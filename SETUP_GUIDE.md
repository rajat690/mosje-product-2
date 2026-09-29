# MoSJE Product 2 – Setup Guide (click by click)

**Scholarship Discovery Assistant: WhatsApp + web companion.** For a non-developer. It takes about 60–90 minutes the first time.

You will:

1. put the code in a **new GitHub repository**;
2. get a **Postgres database** link;
3. create the service on **Render** from the Blueprint;
4. test the **web companion** and the admin page;
5. connect **WhatsApp** (Meta's free test number, your own phone as tester);
6. test the three **entry sources** (organic, outreach link, friend's share link);
7. give the **integration spec** to the Product 1 teams.

> **Synthetic / test data only.** Do not put real student data (CBSE, Jan Aadhaar, etc.) into this deployment. Real data must stay on NIC / MeghRaj.

Product 2 is completely separate from Product 1: separate repository, separate Render service, separate database. Nothing in Product 1 needs to change.

## What you need

* A GitHub account (for example `rajat690`).
* A Render account (the one you use for Product 1 is fine).
* A Meta (Facebook) login with access to your **Meta business account** (the same one used before).
* Your mobile phone with WhatsApp.
* The file `mosje_product2.zip`.

## Step 1 – Create the GitHub repository and upload the files

1. Unzip `mosje_product2.zip` on your computer. You get a folder `mosje_product2` with folders `app`, `data`, `docs`, `templates`, `tests`, `tools` and files like `render.yaml`, `requirements.txt`, `README.md`.
2. Go to **github.com** → top-right **+** → **New repository**.
3. **Repository name:** `mosje-product-2`. **Visibility: Public** (Render's "public repository URL" option needs a public repo; the repo contains only code and synthetic data). Leave "Add a README" **unticked**. Click **Create repository**.
4. On the empty repository page click the link **uploading an existing file**.
5. Open the unzipped `mosje_product2` folder, select **everything inside it** (not the folder itself), and drag it into the browser. GitHub keeps the sub-folders (`app/channels/...`, `app/static/...`) when you drag folders.
6. Wait until all files are listed, write a message such as `First upload`, then click **Commit changes**.
7. **Check the hidden files.** Files whose names start with a dot are often skipped by drag-and-drop (on a Mac they are invisible in Finder). On the repository's main page you must see `.python-version` and `.gitignore`. If either is missing:
   * click **Add file → Create new file**;
   * name: `.python-version`; content (one line): `3.13.5`; click **Commit changes**;
   * again **Add file → Create new file**; name: `.gitignore`; content: copy it from the unzipped folder (open it with Notepad/TextEdit), or at least these lines:

     ```text
     __pycache__/
     .venv/
     *.db
     .env
     ```

8. Check that these exist on GitHub: `render.yaml`, `requirements.txt`, `.python-version`, `app/main.py`, `app/static/companion.html`, `data/scheme_rules_v3.json`, `data/MoSJE_Scholarship_Master_V3.0.xlsx`.
9. Copy the repository URL from the browser address bar, for example `https://github.com/rajat690/mosje-product-2`.

## Step 2 – Choose a database and get its link

Render gives **one free Postgres per workspace**, and Product 1 already uses yours. So the Product 2 Blueprint does **not** create a database. It asks you for a `DATABASE_URL`. Pick **one** option:

| Option | Cost | Good for | Notes |
|---|---|---|---|
| **A. Neon free Postgres** (recommended for the demo) | Free | Easiest, no expiry | External service, free tier. |
| **B. Free Render Postgres in a second Render workspace** | Free | Keeps everything on Render | Free Render Postgres **expires after 30 days**. |
| **C. Paid Render Postgres** in your current workspace | From about US$6–7/month | Long-running demo | No expiry. |

**Option A – Neon**

1. Go to **neon.tech** → **Sign up** (you can use your GitHub login).
2. **Create project**: name `mosje-p2`; Postgres version: the default; **Region: AWS Asia Pacific (Singapore)**. Click **Create**.
3. On the project dashboard click **Connect** (or "Connection string"). Copy the string that starts with `postgresql://` and ends with `?sslmode=require`. Example shape: `postgresql://neondb_owner:xxxx@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
4. Keep it in a private note. This is your **DATABASE_URL**.

**Option B – second Render workspace**

1. Render dashboard → top-left workspace name → **+ New workspace** (for example `mosje-p2`).
2. In that workspace: **+ New → Postgres**. Name `mosje-p2-db`, Region **Singapore**, Plan **Free** → **Create Database**.
3. When it is "Available", open it → **Connect** → copy the **External Database URL**. This is your **DATABASE_URL**. (Create the Blueprint in step 3 in either workspace; the External URL works from anywhere.)

**Option C – paid Render Postgres**

1. Render dashboard (your usual workspace) → **+ New → Postgres**. Name `mosje-p2-db`, Region **Singapore**, choose a paid plan (for example **Basic-256mb**) → **Create Database**.
2. Open it → **Connect** → copy the **Internal Database URL** (works because the web service will be in the same workspace and region). This is your **DATABASE_URL**.
   *(Alternative: uncomment the `databases:` block at the bottom of `render.yaml` as described there.)*

The service creates its tables by itself on first start.

## Step 3 – Create the Render Blueprint

1. Go to **dashboard.render.com** → **+ New** → **Blueprint**.
2. Choose **Public Git Repository**, paste your repository URL (from step 1.9), click **Continue**.
3. **Blueprint name:** `mosje-product-2`. Branch: `main`. Render reads `render.yaml` and shows that it will create:
   * the web service `mosje-p2-api` (free, Singapore);
   * the environment group `mosje-p2-shared` (with the generated `P2_API_KEY` and `WHATSAPP_VERIFY_TOKEN`).
4. Render asks for the values marked "sync: false":
   * **DATABASE_URL**: paste the link from step 2 (**required**);
   * **WHATSAPP_TOKEN**, **WHATSAPP_PHONE_NUMBER_ID**, **WHATSAPP_DISPLAY_NUMBER**, **WHATSAPP_APP_SECRET**: leave them **empty** for now (you fill them in step 6);
   * **P2_API_KEYS**: empty for now (step 9);
   * **ALLOWED_ORIGINS**: empty for now.
5. Click **Apply** (or **Deploy Blueprint**). Wait 3–6 minutes until the service shows **Live**.
6. Open the service `mosje-p2-api`. At the top you see its URL, for example `https://mosje-p2-api.onrender.com`. It may have a suffix, such as `https://mosje-p2-api-x1y2.onrender.com`, if the name was taken. **Write this URL down.** It is called `<service URL>` below.
7. Open `<service URL>/health` in the browser. You should see `"status":"ok"`, `"database":true`, `"db_kind":"postgresql"` and `"whatsapp_configured":false`.

Auto-deploy is **off** (as for Product 1). After you change files on GitHub, open the service and click **Manual Deploy → Deploy latest commit**. After you change `render.yaml`, open the Blueprint and click **Sync** (Manual sync).

## Step 4 – Find the generated secrets

1. Render dashboard → left menu **Environment Groups** (or "Env Groups") → `mosje-p2-shared`.
2. Next to `P2_API_KEY` click the eye icon/**Reveal** → copy. This is the **admin key** and the **admin page password**.
3. Next to `WHATSAPP_VERIFY_TOKEN` click **Reveal** → copy. You will paste it into Meta in step 7.

Keep both private.

## Step 5 – Test the web companion, API docs and admin page (no WhatsApp needed)

1. Open `<service URL>/companion`. A chat opens: tap **English** → **Class 10** → type `Rajasthan` → **SC** → **Female** → **₹1 – 2.5 lakh**. You see scheme cards with links. (The first load after a pause can take up to 1 minute: the free service was asleep.)
2. Tap **Rate this service & get your share link** → pick stars → type a comment or `SKIP`. You get your personal share code `REF-…` and links.
3. Open `<service URL>/companion/demo`. This is a pretend Product 1 page showing the blue **🎓 Find scholarships** button (the embed snippet).
4. Open `<service URL>/admin`. The browser asks for a login: user name `admin` (anything works), password = **P2_API_KEY**. You see referral counts per source system, sessions by channel and **by entry source**, outreach messages, peer referrers, and recent suggestions (masked numbers, India time).
5. Open `<service URL>/docs` → click the green **Authorize** button (top right) → paste **P2_API_KEY** into the **X-API-Key** box → **Authorize** → **Close**. Then open **GET /v1/meta** → **Try it out** → **Execute**. You should get the list of states.

## Step 6 – Meta: create the WhatsApp app and get the test number

Meta changes screen labels from time to time. If a label differs slightly, look for the closest match.

1. Go to **developers.facebook.com** → log in → **My Apps** → **Create App**.
2. App name: `MoSJE Discovery P2`; contact e-mail: yours. Use case: **Connect with customers through WhatsApp** (in older screens: type **Business**, then add the **WhatsApp** product). Business portfolio: choose **your existing business account** (the same one as before). Click **Create app** and confirm your password.
3. In the app's left menu open **WhatsApp → API Setup** (in newer screens: **Use cases → Customize → API Setup** or **Quickstart**).
4. **Temporary access token:** click **Generate access token** (continue through the pop-up). Copy it. This is **WHATSAPP_TOKEN**. It **expires after about 24 hours** (see step 10 for a permanent one).
5. **From:** Meta shows a free **test number** (for example `+1 555 …`). Below it is the **Phone number ID** (a long number, **not** the phone number). Copy it. This is **WHATSAPP_PHONE_NUMBER_ID**.
6. Also write down the test number itself, **digits only with country code** (for example `15551234567`). This is **WHATSAPP_DISPLAY_NUMBER**; it is used to build `wa.me` links.
7. **To:** click **Manage phone number list → Add phone number** → enter **your own mobile** (+91 …) → enter the code WhatsApp sends you. Up to **5** tester numbers can be added (for example Product 1 team members).
8. Optional check: click **Send message** on this page. You should receive Meta's **hello_world** message on your phone.
9. Optional (stronger security): app left menu **App settings → Basic → App secret → Show** → copy. This is **WHATSAPP_APP_SECRET**. When it is set, Product 2 rejects webhook calls that are not signed by Meta.
10. **Put the values into Render:** service `mosje-p2-api` → **Environment** → fill **WHATSAPP_TOKEN**, **WHATSAPP_PHONE_NUMBER_ID**, **WHATSAPP_DISPLAY_NUMBER** (and **WHATSAPP_APP_SECRET** if you copied it) → **Save, rebuild, and deploy** (or **Save changes**, then **Manual Deploy → Deploy latest commit**). Wait until **Live**. `<service URL>/health` now shows `"whatsapp_configured":true`.

## Step 7 – Meta: connect the webhook

1. First **wake the service**: open `<service URL>/health` and wait for `ok`. (Meta gives up if the service is asleep during verification.)
2. In the Meta app: **WhatsApp → Configuration** → **Webhook** → **Edit**.
3. **Callback URL:** `<service URL>/whatsapp/webhook` (for example `https://mosje-p2-api.onrender.com/whatsapp/webhook`).
4. **Verify token:** paste **WHATSAPP_VERIFY_TOKEN** from step 4.
5. Click **Verify and save**. If it fails, check the URL (no extra spaces, `https`, path `/whatsapp/webhook`) and that the token is exactly the same.
6. Under **Webhook fields** click **Manage** → find **messages** → click **Subscribe** → **Done**.

## Step 8 – Test WhatsApp and the three entry sources

**8.1 ORGANIC (found the bot on their own)**

* On your phone, open WhatsApp and send `hi` to the test number (save it as a contact, for example "MoSJE P2 test").
* The bot replies with the language menu. Answer with numbers: `1` (English) → `1` (Class 10) → `Rajasthan` → `1` (SC) → `2` (Male) → `2` (₹1–2.5 lakh). You get up to 5 schemes with links. `1` = more, `2` = rate & share, `3` = start again, `4` = help. `STOP` stops messages, and `hi` starts again.
* In the admin page: **Sessions by entry source** shows `ORGANIC / whatsapp`. Opening `/companion` directly counts as `ORGANIC / web`.
* The first message after the service has been idle can take up to 1 minute. Meta keeps retrying, and duplicates are ignored.

**8.2 OUTREACH (tapped a link from an outreach message)**

1. `<service URL>/docs` → **Authorize** with **P2_API_KEY**.
2. **POST /v1/referrals** → **Try it out** → body (put **your own** mobile, 10 digits):

   ```json
   {"source_system": "p1-rajat", "referrals": [{"external_ref": "TEST-001", "mobile": "98XXXXXXXX", "name": "Rajat Test", "state": "Rajasthan", "class_passed": "X", "category": "OBC", "reason": "PROBABLE"}]}
   ```

   → **Execute** → `created: 1`.
3. **POST /v1/outreach-messages** → body:

   ```json
   {"source_system": "p1-rajat", "message_id": "test-wave-1", "campaign": "Setup test", "channel": "sms", "template_text": "Namaste, find scholarships: {{link}}", "sent_at": "2026-10-01T09:30:00+05:30", "recipients": ["TEST-001"]}
   ```

   → **Execute**. In the response, find `recipients[0].whatsapp_link` and `recipients[0].web_link`.
4. Send the **whatsapp_link** to yourself (for example in an e-mail or WhatsApp note) and tap it on your phone. WhatsApp opens with the text "Hi, I want to find scholarships. Code OM-…-R…" → press **Send**. The bot greets you by first name and shows the facts from the referral → `1` to confirm → remaining questions → schemes.
5. Open the **web_link** in a browser. The companion greets "Rajat" and shows the same facts.
6. **GET /v1/results** with `source_system=p1-rajat` → your sessions show `"entry": {"source": "OUTREACH", "outreach_message_id": "test-wave-1", "recipient_ref": "TEST-001", ...}`. **GET /v1/outreach-messages/test-wave-1** (with `source_system=p1-rajat`) shows `sessions_started`.

**8.3 PEER_REFERRAL (came via a friend's share link)**

1. Finish a chat (WhatsApp or web), choose **Rate this service & get your share link**, rate, then comment or `SKIP`.
2. Copy the web share link (`…/companion?src=referral&ref=REF-…`) and open it in another browser or a private window. Or send the WhatsApp share link to a second tester phone.
3. Admin page → **Peer referrers** shows your code with "friends who started = 1". **Sessions by entry source** shows `PEER_REFERRAL`.

**8.4 Optional: template test.** `/docs` → **POST /whatsapp/send-template** → body `{"to": "91XXXXXXXXXX"}` (your number) → you receive `hello_world`.

## Step 9 – Connect a Product 1 (your build and Team B's)

1. Create one key per Product 1. Use a password generator for long random strings (32+ characters), for example `KEY_RAJAT` and `KEY_TEAMB`.
2. Render → `mosje-p2-api` → **Environment** → **P2_API_KEYS** = `p1-rajat:KEY_RAJAT,p1-teamB:KEY_TEAMB` → **Save, rebuild, and deploy**. `/health` then lists `source_systems_with_keys`.
3. Send each team **only its own key**, through a private channel, plus:
   * `<service URL>`,
   * `INTEGRATION_SPEC.md` / `.docx`,
   * `templates/referrals_template.csv`,
   * `docs/sample_referral_round_trip.md`.
4. Each team: pushes referrals (`POST /v1/referrals`, or CSV upload), registers outreach messages to get links (`POST /v1/outreach-messages`), and polls `GET /v1/results` (or registers a callback with `PUT /v1/source-systems/me`). Team B cannot see your data, and you cannot see theirs.
5. To embed the chat in a Product 1 web app: add one line to the page: `<script src="<service URL>/companion/embed.js" defer></script>`. Put the Product 1 site address in **ALLOWED_ORIGINS** (comma-separated, for example `https://mosje-dashboard.onrender.com`) if they want to call the chat API directly or limit who can embed. See spec section 6.
6. Their test phones must be added as recipients on the Meta test number (step 6.7; maximum 5 numbers in total).

## Step 10 – Important notes

**Free service sleeps.** After 15 minutes without traffic the service sleeps, and the next request wakes it in about 1 minute. The first WhatsApp reply can therefore be slow. Meta retries webhook deliveries, and Product 2 ignores duplicates, so the student still gets exactly one reply. Before a demo, open `/health` to wake it.

**The temporary token expires (~24 h).** When replies stop arriving and `/admin` shows messages with status `failed: HTTP 401`, the token has expired. Generate a new temporary token (step 6.4) and update **WHATSAPP_TOKEN**, or create a **permanent System User token**:

1. Go to **business.facebook.com** → **Settings** (Business settings) → **Users → System users** → **Add** → name `mosje-p2-bot`, role **Admin** → **Create system user**.
2. Select it → **Assign assets** (Add assets) → **Apps** → your app `MoSJE Discovery P2` → **Full control**. Also assign your **WhatsApp account** (WhatsApp Business Account) → **Full control**.
3. Click **Generate new token** → choose the app → token expiry **Never** → permissions **whatsapp_business_messaging** and **whatsapp_business_management** → **Generate token** → copy it (it is shown once).
4. Render → **Environment** → **WHATSAPP_TOKEN** = the new token → **Save, rebuild, and deploy**.

**Test number limits.** Only verified recipient numbers (up to 5) can chat with the test number. Students outside the 24-hour window can only receive approved templates. Real outreach needs a registered business number, a display name and approved templates (for example `scholarship_discovery_invite_en/hi` from Linkage Rules V3.0).

**Updating the code.** Upload the changed files on GitHub (same folders), then **Manual Deploy → Deploy latest commit**. If `render.yaml` changed: Blueprint → **Sync**.

**Database note.** Free Render Postgres (option B) is deleted 30 days after creation unless upgraded. Neon's free tier suspends when idle and wakes automatically (the first query can be slightly slower).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Deploy fails at "pip install" | `.python-version` missing | Create it (step 1.7) and deploy again |
| `/health` shows `"database": false` or deploy crashes | Wrong DATABASE_URL | Copy it again (Neon: include `?sslmode=require`); for a Render DB in another workspace use the **External** URL |
| Meta "Verify and save" fails | Service asleep, wrong URL or token | Open `/health` first; URL must end `/whatsapp/webhook`; paste the token again |
| No reply on WhatsApp | Not subscribed to `messages`, number not a verified recipient, or token expired | Step 7.6; step 6.7; step 10 |
| Admin shows `not_sent: WhatsApp not configured` | WhatsApp env vars empty | Step 6.10 |
| Webhook returns 401 in Meta logs | App secret set but wrong | Copy the App secret again, or clear WHATSAPP_APP_SECRET |
| `whatsapp_link` is null | WHATSAPP_DISPLAY_NUMBER not set and no message received yet | Set WHATSAPP_DISPLAY_NUMBER (step 6.6) |
| Product 1 gets 401 | Wrong key or P2_API_KEYS not saved | Check P2_API_KEYS spelling `source:key,source:key`, then redeploy |
| Embedded widget blocked | ALLOWED_ORIGINS set without that site | Add the site's origin (`https://…`, no trailing slash) |
