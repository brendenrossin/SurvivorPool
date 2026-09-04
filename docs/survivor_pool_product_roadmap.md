# Survivor Pool Dashboard – Open Source vs Product Roadmap
*Last updated: 2025-10-01*

This roadmap lays out a clear strategy for keeping the **Survivor Pool Dashboard** as both a **portfolio project** (public showcase) and a **potential SaaS product** (monetizable private repo).

---

## 1. Strategy Overview

- **Public Showcase Repo (GitHub – Open Source)**  
  Purpose: Demonstrate technical skills (data ingestion, Streamlit dashboards, API integrations).  
  Risk: Someone could fork and self-host.  
  Mitigation: Keep only “lite” features public, license carefully.

- **Private Monetizable Repo (Closed Source / SaaS)**  
  Purpose: Offer as a hosted product or premium install.  
  Value: Handles multi-league support, user auth, automated jobs, and premium insights.  
  Goal: Drive revenue via **SaaS hosting** or **league licenses**.

---

## 2. What to Keep Public (Showcase Repo)

These features highlight your engineering skills but don’t undermine product value:

- ✅ **Single-league support** (Google Sheets ingestion, ESPN scores, basic visuals).  
- ✅ **Core dashboards**: remaining players chart, weekly picks distribution.  
- ✅ **Basic automation scripts** (manual ingestion, update scripts).  
- ✅ **Minimal docs**: setup instructions for a single pool.  
- ✅ **AGPL license** to enforce that forks remain open source.  
- ✅ **Attribution** (README note linking to your SaaS/product site).

👉 Think of this as a “developer toy” version.

---

## 3. What to Keep Private (Product Repo / SaaS)

Reserve these differentiators for the **private repo** you will monetize:

- 🚀 **Multi-league support** (multiple pools on different dashboards).  
- 🚀 **Authentication & roles** (commissioner dashboard, player login).  
- 🚀 **Automated jobs** (cron-based ingestion, scoring, notifications).  
- 🚀 **Premium visuals** (Chaos Meter, Team of Doom, Graveyard board, upset tracker 🐕).  
- 🚀 **Commissioner tools**: invite players, track eliminations, export reports.  
- 🚀 **Custom branding** (logos, themes, white-label options).  
- 🚀 **SaaS deployment** (Railway, Fly.io, or containerized + Stripe payments).  
- 🚀 **Logging & monitoring** (job_meta tables, error handling, observability).  

👉 These are the **must-pay-for** features.

---

## 4. Licensing Approach

- Public repo: Use **AGPL-3.0** (forces derivatives to remain open).  
- Private repo: No license (proprietary).  
- Include attribution + link to your SaaS landing page in the public repo’s README.  

Example:  
> “Want to run your own league without setup? Try the hosted version at [yourdomain.com].”

---

## 5. Marketing & Validation Plan

1. **Reddit Post (r/fantasyfootball, r/survivor, r/nfl)**  
   - Frame as: *“I built a free open-source Survivor Pool dashboard. Thinking about offering a hosted version so commissioners don’t have to self-host—would you use it?”*  

2. **Landing Page MVP**  
   - Simple site (Carrd, Notion, or GitHub Pages).  
   - Collect emails for early access.  

3. **Beta Testers**  
   - Recruit 5–10 pool commissioners to try the SaaS version.  
   - Offer free trial for first season.  

4. **Pricing Experiment**  
   - Options:  
     - Free for first 5 leagues for first season,  
     - If bring your own google sheet:  
        - $25 per league if under 1000 players  
        - $100 per league if over 1000 players  
     - If pick-tracking in app:  
        - $20 **per league per season** for next 5 leagues,   
        - Regular pricing: $2–5 **per player buy-in**, max $100 per league (if under 1000 players), max $250 (if over 1000 players).  

Given what others charge, your lean architecture, and your competitive advantages, here’s a realistic pricing offer for launch:
	•	Free tier: up to 25 entries (or limited feature set) to let small friend/family pools try it.
	•	Standard tier: $29 for up to 150 entries (most small pools).
	•	Pro tier: $59 for up to 500 entries, with advanced analytics, branding, notifications.
	•	Enterprise / custom: for >500 entries or multiple pool packages, custom pricing.

You can also test per-entry pricing (e.g. $0.25 each) or a “pool + host seat” add-on.

---

## 6. Competitive Landscape & Pricing Insights

Several competitor apps exist in the survivor pool space, each offering different features and pricing models:

- **My Survivor Pool**: Offers multi-league support, email reminders, and flexible rules. Pricing typically involves a flat fee per pool, around $25–50. Features include chat and some analytics not currently in this app.

- **Simply SportsWare**: Provides extensive commissioner tools, player management, and social features such as chat and message boards. Pricing is generally subscription-based with tiered plans.

- **Office Pool Stop**: Known for broad office pool management, including survivor pools. Features include email reminders, custom rules, and integration with other pool types. Pricing often uses a rake model or per-entry fees.

- **Survivor Sweat**: Focuses on live scoring and social features like trash talk boards. Pricing is usually per entry ($0.25–0.75) with rake on winnings.

- **RunYourPool**: Offers a full suite of fantasy and survivor pool features including mobile apps, email alerts, and chat. Pricing includes freemium tiers with paid upgrades for premium features.

**This app’s differentiators** include simplicity, transparent pricing, live dashboards with real-time updates, and a leaner feature set that reduces friction and complexity. It avoids heavy social features and rake fees, appealing to users who prefer straightforward, low-cost solutions.

### Pricing Insights Table

| Pricing Model       | Typical Range        | Notes                                  |
|---------------------|----------------------|----------------------------------------|
| Flat per pool       | $25 – $100           | One-time or seasonal fee per league    |
| Per entry          | $0.25 – $0.75        | Charged per player entry                |
| Freemium tiered     | Free + paid upgrades | Basic free tier with paid premium features |
| Rake model          | % of pot or winnings | Common in betting-related pools        |

While many existing apps offer extras like email reminders, chat, and flexible rules, this app focuses on a leaner, more transparent, and lower-friction option that emphasizes ease of use and live data visualization.

---

## 7. Discord Integration for Notifications & Messaging

Discord offers a compelling alternative to traditional SMS or email notifications for survivor pool communication. It provides a lower-friction way to send pick reminders, elimination alerts, and commissioner messages.

Discord bots can programmatically post messages to league-level channels for group notifications and can also send direct messages (DMs) to individual users if permissions allow. This enables both broad announcements and personalized communication without relying on SMS gateways or email providers.

An MVP Discord integration could include:

1. **League-level channel bot posts**: Automated reminders such as “Reminder: submit Week 4 picks” posted to a dedicated league channel.

2. **Optional direct messages for players**: Personalized alerts or confirmations sent as DMs.

3. **Webhook integration with Streamlit jobs**: Connect backend jobs to Discord via webhooks or bot APIs to trigger messages based on game events or deadlines.

Implementation can be simplified using libraries like `discord.py` or direct webhook calls. However, limitations include requiring users to join the Discord server and to allow DMs from the bot, which may require onboarding steps.

---

## 8. Development Roadmap

### ✅ Phase 1 – Backend Infrastructure (COMPLETE)
- [x] **Multi-league database schema** (leagues, users, user_players, league_commissioners tables)
- [x] **Database migration system** (idempotent SQL migration + Python script)
- [x] **Updated SQLAlchemy models** (League, User, UserPlayer, LeagueCommissioner)
- [x] **Added league_id to existing tables** (players, picks)
- [x] **Railway dev environment setup** (web-dev + postgres-dev services)
- [x] **Migration deployed to dev** (League 1 created automatically)

### ✅ Phase 2 – Query Layer & Backward Compatibility (COMPLETE)
- [x] **Created DEFAULT_LEAGUE_ID constant** (backward compatibility with existing single-league)
- [x] **Updated all database queries** to filter by league_id:
  - [x] Dashboard data functions (summary, meme stats, player search)
  - [x] Live scores widget
  - [x] Main app queries
  - [x] Score update jobs (ScoreUpdater class)
  - [x] Sheets ingestion job
- [x] **Tested backward compatibility** (all queries work with multi-league schema)
- [x] **Auto-deploy to Railway dev** (feature/multi-league branch)

### ✅ Phase 3 – URL-Based League Routing (COMPLETE)
- [x] **URL routing implementation**:
  - [x] Each league accessible via query param (?league=slug)
  - [x] Auto-redirect to first league if no param specified
  - [x] Error handling for invalid league slugs
  - [x] `get_league_by_slug()` function for URL lookups
- [x] **League switcher sidebar**:
  - [x] Shows current league name and slug
  - [x] Links to other available leagues
  - [x] Shareable link box for each league
- [x] **Header updates**:
  - [x] League name in main title
  - [x] League slug in subtitle
- [x] **Tested with 2 leagues**:
  - [x] League 1: Rossin Family (0 players)
  - [x] League 2: Test League Alpha (5 players)

### 🚧 Dashboard & Platform (IN FLIGHT)

Runs alongside the multi-league phases — this is the single-league dashboard
that is live in production today, not the SaaS build-out.

- [x] **Weekly picks grid** — replaced the 30-colour stacked bar with a team x
      week grid that leads with the current week.
      Spec: `docs/design/picks-grid-spec.md`.
- [ ] **Upgrade Streamlit** (`1.28.2` → `>=1.35`) — *next up*.
      Unlocks `st.plotly_chart(on_select=...)`, native chart click events, and
      `st.fragment` partial reruns (1.33+), which is also the clean fix for the
      whole page re-querying on every widget interaction. Large version jump on
      an app that deploys straight to production, so it wants its own staging
      soak before merge. Blocks the item below.
- [ ] **Click a grid cell to see who picked that team** — depends on the
      Streamlit upgrade. The grid already draws an invisible scatter trace at
      every cell centre for hover; attaching `customdata=[(week, team)]` makes
      it the click target. Needs a cached `get_pickers(season, week, team)` in
      `dashboard_data.py` and a side panel — `st.columns([3, 1])` with
      `st.dataframe(height=fig.layout.height)` so it matches the grid. Must
      clamp to the current week: revealing *who* picked an unplayed week is a
      worse leak than the count.
- [ ] **UI overhaul of the remaining widgets** — `graveyard.py`,
      `team_of_doom.py`, `survivors.py` share the 30-colour problem, and none of
      the widget modules cache their database reads (`survivors.py` is an N+1).
      See `docs/optimizations/picks-grid-backlog.md`.
- [ ] **Live scores should roll forward on Tuesday.** Once Monday's games are
      final, the widget should show the *next* week's games — still filtered to
      teams somebody has picked. Carried over from the 2025-09-18 working notes;
      never implemented.
- [ ] **Every empty state needs its own message.** Each plot, card and table
      should explain *why* it has nothing to show rather than rendering blank or
      a generic line. Carried over from the same notes; partially done (the
      picks grid and breakdown table have theirs, most widgets do not).
- [ ] **Work through the picks-grid review backlog** —
      `docs/optimizations/picks-grid-backlog.md`.

### 🚧 Phase 4 – League Creation & Management (TODO)
- [ ] **League creation page**:
  - [ ] Form to create new league (name, slug, pick source, season)
  - [ ] Auto-generate unique invite code
  - [ ] Validate league slug uniqueness
  - [ ] Insert into database and redirect to new league URL
- [ ] **Commissioner dashboard**:
  - [ ] View/edit league settings
  - [ ] Display and regenerate invite code
  - [ ] Manage players (add, remove, view)
  - [ ] League stats overview
  - [ ] Export league data
- [ ] **League discovery**:
  - [ ] Public league list page (optional)
  - [ ] Search leagues by name/slug
  - [ ] Join league via invite code

### 📋 Phase 5 – In-App Pick Submission (TODO)
- [ ] **User authentication**:
  - [ ] Login/signup flow
  - [ ] Password hashing (bcrypt)
  - [ ] Session management
  - [ ] Magic link login (passwordless option)
- [ ] **Pick submission**:
  - [ ] Weekly pick form
  - [ ] Team validation (no repeats, check previously used teams)
  - [ ] Game lock enforcement (can't pick after kickoff)
  - [ ] Pick confirmation/edit flow
- [ ] **Player onboarding**:
  - [ ] Join league via invite code
  - [ ] Link user to player profile
  - [ ] Commissioner can manually add players

### 📋 Phase 6 – Premium Features & SaaS Differentiation (TODO)
- [ ] **Custom branding**:
  - [ ] League logo upload
  - [ ] Custom color themes
  - [ ] White-label options
- [ ] **Advanced analytics**:
  - [ ] Expected value (EV) calculator for picks
  - [ ] Crowd wisdom insights (consensus vs outliers)
  - [ ] Historical team performance
  - [ ] Survivor odds calculator
- [ ] **Social features**:
  - [ ] League chat/banter board
  - [ ] Trash talk comments
  - [ ] Weekly power rankings
- [ ] **Notifications**:
  - [ ] Email pick reminders
  - [ ] Elimination alerts
  - [ ] Weekly recap emails
- [ ] **Export tools**:
  - [ ] PDF reports
  - [ ] CSV exports
  - [ ] Season summaries

### 📋 Phase 7 – SaaS Infrastructure & Monetization (TODO)
- [ ] **Payment integration**:
  - [ ] Stripe setup
  - [ ] Subscription tiers (Free, Pro, Premium)
  - [ ] Payment flow
- [ ] **Pricing implementation**:
  - [ ] Free tier: 1 league, Google Sheets only
  - [ ] Pro tier: $25-100/league (unlimited leagues, in-app picks)
  - [ ] Premium tier: Custom branding, advanced analytics
- [ ] **Landing page + marketing**:
  - [ ] Product landing page
  - [ ] Email collection for early access
  - [ ] Feature comparison table
  - [ ] Beta signup flow
- [ ] **Beta testing program**:
  - [ ] Recruit 5-10 commissioners
  - [ ] Free first season for beta testers
  - [ ] Feedback collection system

### 📋 Phase 8 – Public Showcase Repo (TODO)
- [ ] **Strip to single-league only** (fork current repo)
- [ ] **Remove premium features** (keep basic dashboards only)
- [ ] **Add comprehensive docs** (setup guide, architecture)
- [ ] **Apply AGPL-3.0 license**
- [ ] **Deploy public demo** (Streamlit Cloud or Railway free tier)
- [ ] **Add attribution** (link to SaaS version in README)
- [ ] **Post to Reddit** (r/fantasyfootball, r/nfl for validation)

### 📋 Phase 9 – Market Test & Validation (TODO)
- [ ] **Reddit validation post** (gauge interest, collect feedback)
- [ ] **Launch beta waitlist** (collect emails)
- [ ] **Invite first beta cohort** (5-10 commissioners)
- [ ] **Iterate on feedback** (fix bugs, add requested features)
- [ ] **Refine pricing model** (based on beta user willingness to pay)

---

## 9. Long-Term Expansion Ideas

- 📱 **Mobile app** (React Native / Flutter).  
- 🏆 **Fantasy-style features** (side bets, mini games).  
- 📊 **Advanced analytics** (EV of picks, crowd wisdom).  
- 💬 **Social layer** (chat or banter boards inside dashboard).  
- 🤝 **Partnerships** with sportsbooks or fantasy platforms.  

---

## 10. Key Principles

- Showcase enough code to **land jobs & build credibility**.  
- Keep monetizable differentiators **private**.  
- Focus on **SaaS convenience**, not just code.  
- Validate demand **before overbuilding**.  

---

**Next Step:** Decide which branch of your repo becomes the **public showcase** vs. the **private product repo**, and begin stripping features accordingly.