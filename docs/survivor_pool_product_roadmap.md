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

### Phase 1 – Public Showcase (2 weeks)
- [ ] Refactor code to support **single league only**.  
- [ ] Remove multi-league or “extra” features.  
- [ ] Add documentation for setup.  
- [ ] Apply AGPL license.  
- [ ] Deploy demo on Streamlit Cloud.  

### Phase 2 – Private Product (4–6 weeks)
- [ ] Add **multi-league support** (DB schema + tenant handling).  
- [ ] Add **user accounts** (commissioner + player).  
- [ ] Build premium visuals + commissioner tools.  
- [ ] Package SaaS deployment (Dockerfile + Railway/Fly.io).  
- [ ] Integrate **Stripe for payments**.  

### Phase 3 – Market Test (ongoing)
- [ ] Post to Reddit to gauge interest.  
- [ ] Launch landing page + email list.  
- [ ] Invite beta testers.  
- [ ] Refine pricing model.  

---

## 7. Long-Term Expansion Ideas

- 📱 **Mobile app** (React Native / Flutter).  
- 🏆 **Fantasy-style features** (side bets, mini games).  
- 📊 **Advanced analytics** (EV of picks, crowd wisdom).  
- 💬 **Social layer** (chat or banter boards inside dashboard).  
- 🤝 **Partnerships** with sportsbooks or fantasy platforms.  

---

## 8. Key Principles

- Showcase enough code to **land jobs & build credibility**.  
- Keep monetizable differentiators **private**.  
- Focus on **SaaS convenience**, not just code.  
- Validate demand **before overbuilding**.  

---

**Next Step:** Decide which branch of your repo becomes the **public showcase** vs. the **private product repo**, and begin stripping features accordingly.
