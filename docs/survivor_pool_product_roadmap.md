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

- 🚀 **Multi-league support** (multiple pools on one dashboard).  
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
     - $10–20 **per league per season**, or  
     - $2–5 **per player buy-in**.  

---

## 6. Development Roadmap

---

## 🎯 **MVP MILESTONE** - Ready for Beta Testing

**Goal**: Basic multi-league support with Google Sheets ingestion, ready for 5-10 commissioner beta testers

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

### 🚧 Phase 4 – MVP League Management (TODO - REQUIRED FOR BETA)
**Target**: Simple commissioner tools for beta testers

- [ ] **Basic league creation**:
  - [ ] Simple form: league name, commissioner email, Google Sheet URL
  - [ ] Auto-generate league slug from name
  - [ ] Auto-generate unique invite code
  - [ ] Create league and redirect to dashboard
- [ ] **Basic commissioner page**:
  - [ ] View league settings (name, slug, invite code, Google Sheet URL)
  - [ ] Regenerate invite code button
  - [ ] Manual "Refresh from Google Sheets" button
  - [ ] View player list with elimination status
- [ ] **Basic onboarding flow**:
  - [ ] Landing page explaining the product
  - [ ] "Create League" button → form
  - [ ] Post-creation: Show invite URL and setup instructions

**⚠️ DEFER TO V2**: League discovery, public league list, advanced settings

### 🚧 Phase 5 – Basic Authentication (TODO - REQUIRED FOR BETA)
**Target**: Secure league access for beta testers

- [ ] **Simple authentication**:
  - [ ] Magic link login (passwordless, no password DB needed)
  - [ ] Email-based signup
  - [ ] Session management (Streamlit session state)
- [ ] **League access control**:
  - [ ] Only show leagues user has access to in sidebar
  - [ ] Commissioner = creator email has full access
  - [ ] Public URL access requires invite code for first visit
  - [ ] After joining, league saved to user's account
- [ ] **Basic user profile**:
  - [ ] View leagues I'm in (commissioner or player)
  - [ ] Leave league option

**⚠️ DEFER TO V2**: Player pick submission (still use Google Sheets for MVP), advanced roles, password auth

---

## 🚀 **V1 MILESTONE** - Public Beta Launch

**Goal**: In-app pick submission, payments, ready for public launch

### 📋 Phase 6 – In-App Pick Submission (TODO)
- [ ] **Pick submission interface**:
  - [ ] Weekly pick form (select team from available teams)
  - [ ] Team validation (no repeats, check previously used teams)
  - [ ] Game lock enforcement (can't pick after kickoff)
  - [ ] Pick confirmation/edit flow (before lock)
- [ ] **Player onboarding**:
  - [ ] Join league via invite code
  - [ ] Link user account to player profile
  - [ ] Commissioner can manually add players
- [ ] **Pick source migration**:
  - [ ] Support both Google Sheets AND in-app picks
  - [ ] League setting: pick_source = "google_sheets" | "in_app" | "both"
  - [ ] Hybrid mode: Some players use sheets, some use app

### 📋 Phase 7 – SaaS Monetization & Landing Page (TODO)
- [ ] **Landing page + waitlist** (do this FIRST before building payments):
  - [ ] Product landing page (clear value prop, feature screenshots)
  - [ ] Waitlist email collection (Mailchimp or ConvertKit)
  - [ ] Feature showcase (show dashboard screenshots, key features)
  - [ ] Pricing preview (show tiers, no checkout yet)
  - [ ] "Join Waitlist" CTA (collect commissioner emails + league details)
  - [ ] Reddit/Twitter validation post with landing page link
  - [ ] **Goal**: Collect 50-100 waitlist signups to validate demand before building Stripe

- [ ] **Payment integration** (only after validating demand):
  - [ ] Stripe setup (test mode first)
  - [ ] Subscription tiers (Free, Pro, Premium)
  - [ ] Payment flow (checkout, success, failure pages)
  - [ ] Billing portal (manage subscription, cancel, update payment method)
  - [ ] Webhook handling (subscription created, canceled, payment failed)

- [ ] **Simplified pricing tiers**:
  - [ ] **Free**: 1 league, max 20 players, Google Sheets only, basic dashboard (perfect for small family pools)
  - [ ] **Pro** ($50/league/season): Unlimited players, in-app picks, Discord/Slack webhooks, priority support
  - [ ] **Premium** ($150/league/season): Everything in Pro + AI recaps, custom branding, advanced analytics

- [ ] **Billing enforcement**:
  - [ ] Check tier limits on league creation (1 league for free tier)
  - [ ] Check player limits on sheets ingestion (20 players for free tier)
  - [ ] Upgrade prompts when hitting limits ("You've reached the free tier limit of 20 players. Upgrade to Pro for unlimited players!")
  - [ ] Grace period for expired subscriptions (7 days read-only access, then lock)
  - [ ] Email reminders before subscription expires (3 days before, day of, 3 days after)

---

## 🎨 **V2 MILESTONE** - Premium Features & Growth

**Goal**: Build premium differentiators that justify $150/league pricing and create viral moments

### 📋 Phase 8 – AI-Powered Weekly Recaps (TODO - FLAGSHIP PREMIUM FEATURE)
**Why this matters**: This is the #1 differentiator that no other survivor pool app has. It keeps players engaged even after elimination and creates viral moments.

- [ ] **Core LLM recap system** 🤖:
  - [ ] Automated LLM-generated recaps (3-4x per week):
    - [ ] **Thursday Night Recap**: Quick recap of TNF game + survivor impact
    - [ ] **Sunday Recap**: Main recap of all Sunday games + eliminations
    - [ ] **Monday Night Recap**: Final recap of MNF + weekly standings
    - [ ] **Friday Look-Ahead** (optional): Preview of upcoming week's games + pick suggestions
  - [ ] Personalized humor and roasting:
    - [ ] Player-specific call-outs (e.g., "Dave Jones eliminated Week 1 for 3rd straight year")
    - [ ] League-wide trends (e.g., "70% of players picked the Lions - group think strikes again")
    - [ ] Historical comparisons (e.g., "Worst week since 2019 when 40 people picked the Browns")
  - [ ] Analysis and insights:
    - [ ] Biggest upsets and how they affected the pool
    - [ ] Underdog picks that paid off
    - [ ] "Chaos meter" moments (close games, comebacks)
    - [ ] Remaining survivor odds for each player

- [ ] **Discord/Slack integration**:
  - [ ] Auto-post recaps to league Discord/Slack channel
  - [ ] Weekly digest format (markdown for Discord, formatted for Slack)
  - [ ] @mention eliminated players (if permissions allow)
  - [ ] League-specific webhook configuration in settings

- [ ] **Cost-efficient implementation**:
  - [ ] 3-4 LLM calls per week (not real-time, triggered by cron)
  - [ ] Use GPT-3.5 Turbo or Claude Haiku (cheap models, ~$0.001 per 1K tokens)
  - [ ] Estimated cost: $0.10-0.50/league/week (scales well)
  - [ ] Premium-only feature to offset costs
  - [ ] Caching: Store generated recaps in DB, don't regenerate

- [ ] **Technical implementation**:
  - [ ] Cron job triggers after games complete (Thu 11pm, Sun 11pm, Mon 11pm PT)
  - [ ] Fetch week's games, picks, results from DB
  - [ ] Build context for LLM (game results, eliminations, pick distribution)
  - [ ] Pass to LLM with prompt template (see below)
  - [ ] Store generated recap in new `league_recaps` table
  - [ ] Post to Discord/Slack webhook if configured
  - [ ] Show in dashboard (new "Weekly Recaps" section)

- [ ] **Example prompt structure**:
  ```python
  You are a witty NFL analyst writing a recap for a survivor pool league.

  Games this week: {game_results}
  Eliminations: {eliminated_players}
  Notable picks: {underdog_winners}
  Pick distribution: {pick_distribution}

  Write a 200-word recap with:
  1. Biggest storylines from the games
  2. Impact on the survivor pool (eliminations, close calls)
  3. Funny roasts for eliminated players (keep it light and playful)
  4. Look-ahead to next week

  Tone: Humorous, sarcastic, engaging (like Barstool Sports meets The Athletic)
  Format: Use markdown formatting for Discord/Slack
  ```

### 📋 Phase 9 – Additional Premium Features (TODO)
- [ ] **Custom branding**:
  - [ ] League logo upload (S3 or Cloudflare R2 for storage)
  - [ ] Custom color themes (primary, secondary colors)
  - [ ] Custom domain (white-label for enterprise customers)
- [ ] **Advanced analytics**:
  - [ ] Expected value (EV) calculator for picks (based on Vegas odds)
  - [ ] Crowd wisdom insights (consensus vs outliers, "Contrarian Corner")
  - [ ] Historical team performance (W/L records in survivor pools)
  - [ ] Survivor odds calculator (remaining player count + weeks left)
  - [ ] "Power Rankings" (rank remaining players by strength of remaining teams)
- [ ] **Social features**:
  - [ ] League chat/banter board (simple comment threads)
  - [ ] Trash talk comments on picks (before games lock)
  - [ ] Weekly power rankings (commissioner can rank players)
  - [ ] Achievement badges (e.g., "Road Warrior" for road underdog wins)
- [ ] **Notifications**:
  - [ ] Email pick reminders (Mon/Tue before deadline)
  - [ ] Elimination alerts (immediate email when eliminated)
  - [ ] Weekly recap emails (plain text version of LLM recap)
  - [ ] Push notifications (if we build mobile app later)
- [ ] **Export tools**:
  - [ ] PDF season summary report (at end of season)
  - [ ] CSV exports (all picks, all players, game results)
  - [ ] Historical data for multi-year leagues

### 📋 Phase 10 – Public Showcase Repo (TODO - Portfolio Piece)
**Goal**: Create open-source version to showcase technical skills while protecting premium features

- [ ] **Fork & strip features**:
  - [ ] Fork current repo to new "survivor-pool-lite" repo
  - [ ] Remove multi-league support (single league only)
  - [ ] Remove all premium features (AI recaps, custom branding, advanced analytics)
  - [ ] Keep basic dashboards only (picks chart, donut chart, live scores)
  - [ ] Remove authentication code
- [ ] **Documentation**:
  - [ ] Comprehensive README with setup instructions
  - [ ] Architecture overview (data flow, caching strategy)
  - [ ] Deployment guide (Railway, Streamlit Cloud)
  - [ ] Contributing guidelines
- [ ] **Licensing & attribution**:
  - [ ] Apply AGPL-3.0 license (forces derivatives to remain open)
  - [ ] Add prominent link to SaaS version in README
  - [ ] Add "Want to run multiple leagues? Try the hosted version at [yourdomain.com]"
- [ ] **Public demo**:
  - [ ] Deploy to Streamlit Cloud or Railway free tier
  - [ ] Link to demo in README
  - [ ] Post to r/fantasyfootball, r/nfl, r/programming for validation

---

## 7. Long-Term Expansion Ideas

### **High-Value Differentiators** (Premium Features)

- 🤖 **AI-Powered League Personality** (Flagship Premium Feature):
  - Weekly LLM-generated recaps with humor and roasting
  - Auto-post to Discord/Slack (3-4x per week)
  - Personalized player call-outs and league-wide trends
  - Cost-efficient: $0.10-0.50/league/week (3-4 LLM calls)
  - **Why it's a killer feature:**
    - No other survivor pool app has this
    - Engages players even after elimination
    - Creates viral moments ("Dave Jones eliminated Week 1 for 3rd year in a row")
    - Low cost, high perceived value
    - Sticky feature (keeps commissioners renewing)

### **Standard Expansion Ideas**

- 📱 **Mobile app** (React Native / Flutter)
- 🏆 **Fantasy-style features** (side bets, mini games, prop bets)
- 📊 **Advanced analytics** (EV of picks, crowd wisdom, historical trends)
- 💬 **Social layer** (in-app chat, banter boards, comment threads)
- 🤝 **Partnerships** (sportsbooks, fantasy platforms, Discord bots)
- 🎮 **Gamification** (achievements, badges, leaderboards across all leagues)
- 📧 **Email digest** (weekly recap emails with LLM-generated content)
- 🎙️ **Audio recaps** (text-to-speech version of LLM recaps for podcasts)

---

## 8. Key Principles

- Showcase enough code to **land jobs & build credibility**.  
- Keep monetizable differentiators **private**.  
- Focus on **SaaS convenience**, not just code.  
- Validate demand **before overbuilding**.  

---

**Next Step:** Decide which branch of your repo becomes the **public showcase** vs. the **private product repo**, and begin stripping features accordingly.
