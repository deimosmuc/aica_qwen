# Deployment – AI Circuit Architect → Alibaba Cloud ECS

Hosts the app at **https://qwen.rocu.de**, protected by **HTTPS (Let's Encrypt)**
and **Basic Auth** (jurors only). The Docker image is built automatically by a
**GitHub Action** and pulled onto an **Ubuntu 24.04** ECS server.

> **Golden rule:** No password and no API key ever goes into Git. All secrets
> live only on the server in `app.env` and `caddy.env` (both gitignored).

The flow in one picture:

```
git push  ──►  GitHub Action builds image  ──►  GHCR (ghcr.io, private)
                                                     │
                                                     ▼
                          ECS server: docker compose pull + up
                                                     │
              Browser ──HTTPS──► Caddy (Basic Auth) ──► app container :8000
```

---

## Part A — One-time: GitHub repo & first build

1. **Create a private repo on GitHub** (it does not exist yet):
   ```bash
   gh repo create <your-repo> --private --source . --remote origin
   ```
   (Or create it in the web UI, then `git remote add origin git@github.com:<user>/<repo>.git`.)

2. **Push `main`:**
   ```bash
   git push -u origin main
   ```

3. The push **starts the GitHub Action automatically**. Watch it in the repo's
   **Actions** tab until it is green. The image then appears under the **Packages**
   tab as `ghcr.io/<user>/<repo>` with tag `latest`.

---

## Part B — One-time: set up the ECS server (Ubuntu 24.04)

4. **Create the ECS instance** (Ubuntu 24.04). Note its **public IP**.

5. **Open the firewall (Security Group):**
   - Port **443** (HTTPS) — open to the world
   - Port **80** (needed for the Let's Encrypt validation) — open to the world
   - Port **22** (SSH) — ideally restricted to your own IP only

6. **DNS:** create an **A-record** `qwen.rocu.de` → the ECS public IP.
   Verify before continuing:
   ```bash
   ping qwen.rocu.de        # must resolve to the ECS IP
   ```
   > HTTPS will fail until DNS points at the server, so don't skip this check.

7. **SSH into the server:**
   ```bash
   ssh root@qwen.rocu.de        # or ssh <user>@<public-ip>
   ```

8. **Install Docker** (Engine + Compose plugin):
   ```bash
   curl -fsSL https://get.docker.com | sh
   docker --version && docker compose version   # confirm both work
   ```

9. **Log in to GHCR** (the image is private):
   - On GitHub create a **Personal Access Token (classic)** with scope
     **`read:packages`**.
   - On the server:
     ```bash
     echo <YOUR_PAT> | docker login ghcr.io -u <your-github-user> --password-stdin
     ```

---

## Part C — One-time: configuration on the server

10. **Get the deploy files onto the server.** Easiest is to clone the repo:
    ```bash
    git clone https://github.com/<user>/<repo>.git
    cd <repo>/deploy
    ```
    You need `docker-compose.yml`, `../Caddyfile`, `app.env`, `caddy.env` reachable
    from one working directory. Simplest: copy the Caddyfile next to the compose
    file:
    ```bash
    cp ../Caddyfile .
    ```
    (Then the compose file's `./Caddyfile` mount works as-is.)

11. **Create `app.env`** from the template and fill in real values:
    ```bash
    cp app.env.example app.env
    nano app.env
    ```
    - `APP_IMAGE=ghcr.io/<user>/<repo>:latest`
    - `QWEN_API_KEY=` your **fresh** Qwen key (see security note below)
    - leave the `GUARD_*` defaults (keeps the $35 cost cap active)

12. **Create `caddy.env`** with the juror login:
    ```bash
    cp caddy.env.example caddy.env
    # generate the password hash (never store the plaintext):
    docker run --rm caddy caddy hash-password --plaintext '<juror-password>'
    nano caddy.env     # set BASIC_AUTH_USER=juror and paste the hash into BASIC_AUTH_HASH
    ```

---

## Part D — Start & verify

13. **Launch the stack:**
    ```bash
    docker compose pull
    docker compose up -d
    ```

14. **Watch Caddy fetch the certificate** (takes a few seconds):
    ```bash
    docker compose logs -f caddy
    ```
    Then open **https://qwen.rocu.de** — you should get a login prompt, then the app.

15. **Sanity check from a terminal:**
    ```bash
    curl -I https://qwen.rocu.de                 # → 401 Unauthorized (auth works)
    curl -I -u juror:<password> https://qwen.rocu.de   # → 200 OK
    ```
    The certificate should be valid (no browser warning).

---

## Part E — Update loop (every change after that)

16. Locally:
    ```bash
    git push
    ```
    The Action rebuilds and pushes the new image. Then on the server:
    ```bash
    docker compose pull && docker compose up -d
    ```
    **Never** edit files directly on the server. Secrets stay in `app.env` /
    `caddy.env` and are reused automatically.

---

## Security notes

- **Rotate the Qwen key before the public demo.** The key currently in your local
  `.env` was on disk in plaintext — generate a new one in the Alibaba console and
  put it **only** in `app.env` on the server.
- `app.env` and `caddy.env` live **only on the server** and are gitignored — they
  are never committed.
- The API Guard stays on (`GUARD_BUDGET_USD=35.0`) as a hard cost brake.

## Troubleshooting

- **Cert not issued / HTTPS fails:** DNS A-record not pointing at the server yet,
  or port 80/443 closed in the Security Group. Recheck steps 5–6, then
  `docker compose restart caddy`.
- **`docker compose pull` says "denied":** GHCR login expired or PAT lacks
  `read:packages`. Repeat step 9.
- **App shows Mock Mode banner:** `QWEN_API_KEY` empty in `app.env`. Fill it in and
  `docker compose up -d` again.
