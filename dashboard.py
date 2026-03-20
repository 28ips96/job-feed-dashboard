"""
dashboard.py — Job Feed v3 Dashboard
Four-tab UI: Discover · Pipeline · Network · Outreach
Run: python3 dashboard.py  →  http://localhost:5050
"""
import json
import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote_plus
from flask import Flask, render_template_string, request, jsonify, send_file

sys.path.insert(0, os.path.dirname(__file__))
from db import (init_db, get_jobs, update_job_status, get_stats, get_connection,
                get_contacts, insert_contact, update_contact, delete_contact,
                log_touchpoint, get_touchpoints, apply_enrichment)
from config import DB_PATH, FEED_DIR, OUTPUT_DIR, APP_STATUSES

app = Flask(__name__)


# ─── LINKEDIN URL BUILDER ─────────────────────────────────────────────────────

_RECRUITER_TERMS = {
    "Product Manager":            '"technical recruiter" OR "talent acquisition" product',
    "AI/ML Product Manager":      '"technical recruiter" OR "talent acquisition" AI ML',
    "Technical Program Manager":  '"technical recruiter" OR "talent acquisition" program',
    "Strategy & Operations":      '"recruiter" OR "talent acquisition" strategy operations',
    "Finance & Strategy / FP&A":  '"recruiter" OR "talent acquisition" finance',
    "Consulting":                 '"recruiter" OR "talent partner" consulting',
    "Customer Success":           '"recruiter" OR "talent acquisition" customer success',
    "Product Marketing":          '"recruiter" OR "talent acquisition" product marketing',
    "Solutions / Pre-Sales":      '"recruiter" OR "talent acquisition" solutions',
}


def build_linkedin_urls(company, search_type, role_category=None, job_title=None):
    """
    Generate LinkedIn People Search URLs optimized for each search type.
    Uses quoted company name, role-specific recruiter terms, US geo filter,
    and connection degree filtering. Returns dict with 1st/2nd/3rd degree URLs.
    """
    base = "https://www.linkedin.com/search/results/people/"
    co = f'"{company}"'
    geo = "&geoUrn=%5B%22103644278%22%5D"   # United States

    if search_type == "alumni":
        keywords = f'{co} "Kelley School of Business" OR "Indiana University" MBA'

    elif search_type == "hiring_team":
        terms = _RECRUITER_TERMS.get(role_category or "", '"recruiter" OR "talent acquisition"')
        keywords = f'{co} {terms}'

    elif search_type == "same_role":
        if job_title:
            clean = re.sub(r'^(senior|sr\.?|lead|principal|staff|associate|junior)\s+',
                           '', job_title.lower())
            clean = re.sub(r'\s*[-–,|/]\s*(remote|hybrid|us|usa|sf|nyc|new york|'
                           r'san francisco|austin|seattle).*$', '', clean, flags=re.IGNORECASE)
            clean = re.sub(r'\s*\(.*?\)\s*', '', clean).strip()
            skip = {'the', 'and', 'for', 'with', 'at', 'in', 'of', 'a', 'an', 'to', 'or'}
            words = [w for w in clean.split() if len(w) > 2 and w not in skip][:4]
            title_terms = ' '.join(words)
        else:
            title_terms = role_category or "product manager"
        keywords = f'{co} "{title_terms}"'

    else:
        keywords = f'{co} {search_type}'

    encoded = quote_plus(keywords)
    return {
        "1st": f"{base}?keywords={encoded}&network=%5B%22F%22%5D{geo}&origin=GLOBAL_SEARCH_HEADER",
        "2nd": f"{base}?keywords={encoded}&network=%5B%22S%22%5D{geo}&origin=GLOBAL_SEARCH_HEADER",
        "3rd": f"{base}?keywords={encoded}&network=%5B%22O%22%5D{geo}&origin=GLOBAL_SEARCH_HEADER",
    }

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Feed Dashboard</title>
<style>
:root {
  --navy:#1C2E5A; --slate:#3B5280; --indigo:#4F46E5; --purple:#7C3AED;
  --bg:#F3F4F6; --card:#FFF; --border:#E5E7EB;
  --text:#111827; --muted:#6B7280; --green:#059669; --amber:#D97706; --red:#DC2626;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text)}
/* ── Header ── */
.header{background:linear-gradient(135deg,var(--indigo),var(--purple));padding:16px 32px;
  display:flex;justify-content:space-between;align-items:center}
.header h1{color:#fff;font-size:20px;font-weight:700}
.header .sub{color:#C7D2FE;font-size:12px;margin-top:2px}
.hbtns{display:flex;gap:8px}
.hbtn{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.25);
  padding:7px 14px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:500}
.hbtn:hover{background:rgba(255,255,255,.25)}
/* ── Stats bar ── */
.stats-bar{display:flex;gap:10px;padding:14px 32px;overflow-x:auto}
.stat-card{background:var(--card);border-radius:10px;padding:12px 18px;min-width:120px;border:1px solid var(--border)}
.stat-card .lbl{font-size:10px;text-transform:uppercase;color:var(--muted);letter-spacing:.05em}
.stat-card .val{font-size:20px;font-weight:700;margin-top:3px}
/* ── Tab nav ── */
.tab-nav{display:flex;gap:0;padding:0 32px;border-bottom:2px solid var(--border);margin-bottom:0}
.tab-btn{padding:10px 24px;font-size:14px;font-weight:600;cursor:pointer;border:none;
  background:transparent;color:var(--muted);border-bottom:3px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab-btn.active{color:var(--indigo);border-bottom-color:var(--indigo)}
/* ── Tab panels ── */
.tab-panel{display:none;padding:20px 32px 40px}
.tab-panel.active{display:block}
/* ── Filters ── */
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.filters select,.filters input{padding:7px 11px;border-radius:8px;border:1px solid var(--border);font-size:13px;background:var(--card)}
.filters input{width:220px}
.pill{padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;
  border:2px solid transparent;transition:all .15s}
.pill.active{border-color:var(--indigo)}
.pill-pm{background:#D1ECF9;color:#0B5574}
.pill-aipm{background:#E0D4FF;color:#3D0C8E}
.pill-tpm{background:#E8D9F7;color:#4B1C80}
.pill-strat{background:#FFF3CD;color:#7D5A00}
.pill-fin{background:#D4EDDA;color:#155724}
.pill-cons{background:#FCE4D4;color:#7B2D0A}
.pill-pmm{background:#FCE7F3;color:#831843}
.pill-cs{background:#DCFCE7;color:#14532D}
.pill-sol{background:#FEF9C3;color:#713F12}
/* ── Job Grid (Discover) ── */
.job-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.job-card{background:var(--card);border-radius:12px;padding:16px;border:1px solid var(--border);
  cursor:pointer;transition:box-shadow .15s,transform .1s;position:relative}
.job-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-1px)}
.score-badge{position:absolute;top:12px;right:12px;font-size:14px;font-weight:800;
  padding:3px 9px;border-radius:7px}
.score-fire{background:#DCFCE7;color:#065F46}   /* 🔥 80+ */
.score-high{background:#D1FAE5;color:#065F46}   /* ✅ 60+ */
.score-med{background:#FEF3C7;color:#92400E}    /* 🟡 40+ */
.score-low{background:#F3F4F6;color:#6B7280}    /* ⚪ <40  */
.jc-company{font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.jc-title{font-size:14px;font-weight:600;margin:4px 0;padding-right:52px;line-height:1.3}
.jc-meta{font-size:11px;color:var(--muted);display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.jc-clusters{font-size:10px;color:#818CF8;margin-top:6px}
.jc-actions{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.mba-badge{font-size:10px;background:#FFF8E1;color:#7D5A00;border:1px solid #FDD835;
  border-radius:4px;padding:2px 6px;margin-top:4px;display:inline-block}
/* ── Card buttons ── */
.cbtn{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;
  cursor:pointer;border:1px solid var(--border);background:var(--card);transition:all .1s;
  text-decoration:none;color:var(--text);display:inline-block}
.cbtn:hover{background:var(--bg)}
.cbtn-primary{background:var(--indigo);color:#fff;border-color:var(--indigo)}
.cbtn-apply{background:#059669;color:#fff;border-color:#059669}
.cbtn-rebase{background:#7C3AED;color:#fff;border-color:#7C3AED}
.cbtn-save{background:#F59E0B;color:#fff;border-color:#F59E0B}
/* ── Kanban ── */
.kanban{display:flex;gap:14px;overflow-x:auto;min-height:60vh;padding-bottom:20px}
.kanban-col{min-width:240px;max-width:280px;flex:1;display:flex;flex-direction:column}
.col-header{padding:10px 14px;border-radius:10px 10px 0 0;font-size:13px;font-weight:700;
  display:flex;justify-content:space-between;align-items:center;color:#fff}
.col-body{flex:1;background:rgba(0,0,0,.03);border-radius:0 0 10px 10px;padding:8px;
  display:flex;flex-direction:column;gap:8px;overflow-y:auto;max-height:65vh}
.col-new .col-header{background:#818CF8}
.col-saved .col-header{background:#F59E0B}
.col-applying .col-header{background:#3B82F6}
.col-applied .col-header{background:#8B5CF6}
.col-interviewing .col-header{background:#10B981}
.col-offer .col-header{background:#059669}
.pipeline-card{background:var(--card);border-radius:9px;padding:12px;
  border:1px solid var(--border);cursor:pointer;transition:box-shadow .15s}
.pipeline-card:hover{box-shadow:0 3px 10px rgba(0,0,0,.07)}
.pc-company{font-size:11px;color:var(--muted);font-weight:600}
.pc-title{font-size:13px;font-weight:600;margin:3px 0}
.pc-meta{font-size:10px;color:var(--muted);display:flex;gap:6px;flex-wrap:wrap;margin-top:5px}
.pc-notes{font-size:10px;color:var(--muted);font-style:italic;margin-top:4px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.rejected-section{margin-top:20px}
.rejected-header{font-size:13px;font-weight:600;color:var(--muted);padding:6px 0;
  cursor:pointer;display:flex;align-items:center;gap:6px}
.rejected-cards{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
/* ── Network tab ── */
.network-targets{margin-bottom:32px}
.network-targets h2{font-size:16px;font-weight:700;margin-bottom:10px}
.net-search{padding:7px 11px;border-radius:8px;border:1px solid var(--border);font-size:13px;width:260px;margin-bottom:14px}
.company-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.company-card{background:var(--card);border-radius:10px;padding:16px;border:1px solid var(--border);position:relative;transition:box-shadow .15s}
.company-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.07)}
.cc-name{font-size:15px;font-weight:700;margin-bottom:4px;padding-right:60px}
.cc-meta{font-size:11px;color:var(--muted);margin-bottom:10px}
.cc-links{display:flex;flex-direction:column;gap:2px}
.cc-section-label{font-size:11px;font-weight:600;color:var(--muted);margin:7px 0 3px}
.cc-deg-row{display:flex;gap:6px}
.cc-deg{font-size:12px;text-decoration:none;padding:3px 9px;border-radius:5px;font-weight:600;transition:opacity .12s}
.cc-deg:hover{opacity:.75;text-decoration:underline}
.cc-deg-1{color:#4F46E5;background:#EEF2FF;font-size:13px}
.cc-deg-2{color:#374151;background:#F3F4F6}
.cc-deg-3{color:#9CA3AF;background:#F9FAFB;font-size:11px}
.crm-section h2{font-size:16px;font-weight:700;margin-bottom:14px}
.crm-filters{display:flex;gap:8px;margin-bottom:12px}
.contact-table{width:100%;border-collapse:collapse;background:var(--card);
  border-radius:10px;overflow:hidden;border:1px solid var(--border);font-size:13px}
.contact-table th{background:var(--slate);color:#fff;padding:9px 12px;text-align:left;
  font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.contact-table td{padding:9px 12px;border-bottom:1px solid var(--border)}
.contact-table tr:hover td{background:#F9FAFB}
.rel-badge{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
.rel-cold{background:#F3F4F6;color:#6B7280}
.rel-warm{background:#FEF3C7;color:#92400E}
.rel-connected{background:#D1FAE5;color:#065F46}
.rel-replied{background:#DBEAFE;color:#1E40AF}
/* ── Modal ── */
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.5);z-index:100;justify-content:center;align-items:center}
.modal-overlay.active{display:flex}
.modal{background:var(--card);border-radius:16px;max-width:720px;width:90%;
  max-height:88vh;overflow-y:auto;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.2)}
.modal h2{font-size:18px;margin-bottom:4px}
.modal .mc{color:var(--muted);font-size:13px;margin-bottom:16px}
.modal-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.mf .lbl{color:var(--muted);font-size:11px}
.mf .val{font-weight:600;margin-top:2px;font-size:13px}
.modal textarea{width:100%;padding:9px;border-radius:8px;border:1px solid var(--border);
  font-size:13px;font-family:inherit;resize:vertical;min-height:60px}
.modal-actions{display:flex;gap:8px;margin-top:18px;flex-wrap:wrap}
.rebase-out{margin-top:16px;background:#F9FAFB;border:1px solid var(--border);
  border-radius:10px;padding:16px;font-size:12px;white-space:pre-wrap;
  font-family:'SF Mono','Menlo',monospace;max-height:300px;overflow-y:auto;display:none}
/* ── Status select ── */
.status-sel{padding:4px 8px;border-radius:6px;border:1px solid var(--border);font-size:12px;cursor:pointer}
/* ── Contact modal ── */
.contact-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.contact-form input,.contact-form select,.contact-form textarea{
  padding:8px 10px;border-radius:8px;border:1px solid var(--border);font-size:13px;font-family:inherit;width:100%}
.contact-form .full{grid-column:1/-1}
/* ── Toast ── */
.toast{position:fixed;bottom:24px;right:24px;background:var(--navy);color:#fff;
  padding:11px 18px;border-radius:10px;font-size:13px;font-weight:500;
  box-shadow:0 4px 12px rgba(0,0,0,.15);transform:translateY(100px);opacity:0;
  transition:all .3s;z-index:200}
.toast.show{transform:translateY(0);opacity:1}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>📋 Job Feed Dashboard</h1>
    <div class="sub" id="lastRun">Loading...</div>
  </div>
  <div class="hbtns">
    <button class="hbtn" onclick="runFeed()">🔄 Fetch Now</button>
    <button class="hbtn" onclick="exportExcel()">📊 Export Excel</button>
  </div>
</div>

<div class="stats-bar" id="statsBar"></div>

<div class="tab-nav">
  <button class="tab-btn active" onclick="setTab('discover',this)">Discover</button>
  <button class="tab-btn" onclick="setTab('pipeline',this)">Pipeline</button>
  <button class="tab-btn" onclick="setTab('network',this)">Network</button>
  <button class="tab-btn" onclick="setTab('outreach',this)">Outreach</button>
</div>

<!-- ── DISCOVER TAB ────────────────────────────────────────────────────── -->
<div class="tab-panel active" id="tab-discover">
  <div class="filters">
    <input type="text" id="discoverSearch" placeholder="Search company, role, keyword…" oninput="renderDiscover()">
    <select id="discoverDays" onchange="renderDiscover()">
      <option value="0">All time</option>
      <option value="1">Last 24h</option>
      <option value="3">Last 3 days</option>
      <option value="7" selected>Last 7 days</option>
      <option value="14">Last 14 days</option>
      <option value="30">Last 30 days</option>
    </select>
    <select id="discoverScore" onchange="renderDiscover()">
      <option value="0">All scores</option>
      <option value="80">🔥 80+ Fire</option>
      <option value="60">✅ 60+ Strong</option>
      <option value="40">🟡 40+ OK</option>
    </select>
    <select id="discoverVisa" onchange="renderDiscover()">
      <option value="">All visa</option>
      <option value="known">✅ Known sponsors</option>
    </select>
    <span class="pill pill-pm" data-cat="Product Manager" onclick="togglePill(this)">🚀 PM</span>
    <span class="pill pill-aipm" data-cat="AI/ML Product Manager" onclick="togglePill(this)">🤖 AI/ML PM</span>
    <span class="pill pill-pmm" data-cat="Product Marketing" onclick="togglePill(this)">📣 PMM</span>
    <span class="pill pill-tpm" data-cat="Technical Program Manager" onclick="togglePill(this)">⚙️ TPM</span>
    <span class="pill pill-strat" data-cat="Strategy & Operations" onclick="togglePill(this)">📊 Strat/Ops</span>
    <span class="pill pill-fin" data-cat="Finance & Strategy / FP&A" onclick="togglePill(this)">💰 FP&A</span>
    <span class="pill pill-cons" data-cat="Consulting" onclick="togglePill(this)">🏛 Consulting</span>
    <span class="pill pill-cs" data-cat="Customer Success" onclick="togglePill(this)">🤝 CS</span>
    <span class="pill pill-sol" data-cat="Solutions / Pre-Sales" onclick="togglePill(this)">🎯 Solutions</span>
  </div>
  <div class="job-grid" id="discoverGrid"></div>
</div>

<!-- ── PIPELINE TAB ──────────────────────────────────────────────────────── -->
<div class="tab-panel" id="tab-pipeline">
  <div class="kanban" id="kanbanBoard"></div>
  <div class="rejected-section">
    <div class="rejected-header" onclick="toggleRejected()">
      <span id="rejectedArrow">▶</span> Rejected / Withdrawn
      <span id="rejectedCount" style="font-weight:400;font-size:12px"></span>
    </div>
    <div id="rejectedCards" style="display:none" class="rejected-cards"></div>
  </div>
</div>

<!-- ── NETWORK TAB ──────────────────────────────────────────────────────── -->
<div class="tab-panel" id="tab-network">
  <div class="network-targets">
    <h2>🎯 Networking Targets
      <span style="font-size:12px;font-weight:400;color:var(--muted);margin-left:8px">Top 40 companies by best job score</span>
    </h2>
    <input type="text" class="net-search" id="networkSearch" placeholder="Filter by company…" oninput="renderNetwork()">
    <div class="company-cards" id="networkCompanies"></div>
  </div>
</div>

<!-- ── OUTREACH TAB ───────────────────────────────────────────────────────── -->
<div class="tab-panel" id="tab-outreach">
  <div class="crm-section">
    <h2 style="margin-bottom:14px">🤝 Outreach Tracker
      <button class="cbtn cbtn-primary" onclick="openContactModal(null)" style="margin-left:12px;font-size:12px;padding:5px 14px">+ Add Contact</button>
    </h2>
    <div class="crm-filters">
      <input type="text" class="filters input" id="crmSearch2" placeholder="Filter by company or name…" oninput="renderCRM()" style="padding:7px 11px;border-radius:8px;border:1px solid var(--border);font-size:13px">
      <select id="crmRelFilter" onchange="renderCRM()" style="padding:7px 11px;border-radius:8px;border:1px solid var(--border);font-size:13px">
        <option value="">All relationships</option>
        <option value="cold">Cold</option>
        <option value="warm">Warm</option>
        <option value="connected">Connected</option>
        <option value="replied">Replied</option>
      </select>
    </div>
    <table class="contact-table" id="contactTable">
      <thead><tr>
        <th>Name</th><th>Company</th><th>Title</th><th>Status</th>
        <th>Last Contact</th><th>Next Follow-up</th><th>Notes</th><th>Actions</th>
      </tr></thead>
      <tbody id="contactBody"></tbody>
    </table>
  </div>
  <div style="margin-top:32px">
    <h2 style="font-size:16px;font-weight:700;margin-bottom:14px">📧 Outreach Templates</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px">
      <div style="background:var(--card);border-radius:10px;padding:16px;border:1px solid var(--border)">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px">Alumni Intro — Cold</div>
        <pre style="font-size:11px;line-height:1.5;white-space:pre-wrap;color:var(--muted)">Hi [Name],
I noticed we're both Kelley alumni — small world! I'm currently exploring [role type] roles and saw that [Company] is doing exciting work in [area]. Would love to connect briefly if you have 15 min.
— Dinesh</pre>
      </div>
      <div style="background:var(--card);border-radius:10px;padding:16px;border:1px solid var(--border)">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px">Recruiter — Active Role</div>
        <pre style="font-size:11px;line-height:1.5;white-space:pre-wrap;color:var(--muted)">Hi [Name],
I applied for the [Role] position at [Company] (req ID: [ID]). With my background at Amadeus in travel tech and an MBA from Kelley, I think I'm a strong match. Happy to answer any questions!
— Dinesh</pre>
      </div>
      <div style="background:var(--card);border-radius:10px;padding:16px;border:1px solid var(--border)">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px">Warm — Follow-up</div>
        <pre style="font-size:11px;line-height:1.5;white-space:pre-wrap;color:var(--muted)">Hi [Name],
Following up on my earlier note — still very interested in [Company]. I recently [new achievement/update]. Would love to stay on your radar for [team/role].
— Dinesh</pre>
      </div>
    </div>
  </div>
</div>

<!-- ── JOB DETAIL MODAL ──────────────────────────────────────────────────── -->
<div class="modal-overlay" id="jobModalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal" id="jobModal"></div>
</div>

<!-- ── CONTACT MODAL ─────────────────────────────────────────────────────── -->
<div class="modal-overlay" id="contactModalOverlay" onclick="if(event.target===this)closeContactModal()">
  <div class="modal" id="contactModal" style="max-width:560px">
    <h2 id="contactModalTitle">Add Contact</h2>
    <div style="margin-top:16px" class="contact-form" id="contactForm"></div>
    <div class="modal-actions">
      <button class="cbtn cbtn-primary" onclick="saveContact()">💾 Save</button>
      <button class="cbtn" onclick="closeContactModal()">Cancel</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let allJobs = [];
let contacts = [];
let activePills = new Set();
let editingContactId = null;

const PIPELINE_STATUSES = ['saved','applying','applied','interviewing','offer'];
const STATUS_LABELS = {
  new:'📥 New', saved:'⭐ Saved', applying:'✏️ Applying',
  applied:'📤 Applied', interviewing:'🎤 Interviewing',
  offer:'🎉 Offer', rejected:'❌ Rejected', withdrawn:'🚫 Withdrawn'
};
const CAT_PILLS = {
  'Product Manager':'pill-pm','AI/ML Product Manager':'pill-aipm',
  'Product Marketing':'pill-pmm','Technical Program Manager':'pill-tpm',
  'Strategy & Operations':'pill-strat','Finance & Strategy / FP&A':'pill-fin',
  'Consulting':'pill-cons','Customer Success':'pill-cs',
  'Solutions / Pre-Sales':'pill-sol'
};

// ── Data loading ─────────────────────────────────────────────────────────────
async function loadAll() {
  const [jobsRes, statsRes, contactsRes] = await Promise.all([
    fetch('/api/jobs?days=30'), fetch('/api/stats'), fetch('/api/contacts')
  ]);
  allJobs = await jobsRes.json();
  contacts = await contactsRes.json();
  const s = await statsRes.json();
  renderStats(s);
  renderDiscover();
  renderPipeline();
  renderNetwork();
}

function renderStats(s) {
  document.getElementById('lastRun').textContent =
    `${s.total} jobs (7d) · Avg score: ${s.avg_match_score} · ${s.visa_sponsors} visa sponsors`;
  const cards = [
    {label:'Total (7d)',val:s.total,color:'#4F46E5'},
    {label:'High Fit 70+',val:s.high_fit||0,color:'#059669'},
    {label:'Applied',val:(s.by_status||{}).applied||0,color:'#8B5CF6'},
    {label:'Interviewing',val:(s.by_status||{}).interviewing||0,color:'#10B981'},
    {label:'Visa Sponsors',val:s.visa_sponsors,color:'#D97706'},
  ];
  document.getElementById('statsBar').innerHTML = cards.map(c=>
    `<div class="stat-card"><div class="lbl">${c.label}</div><div class="val" style="color:${c.color}">${c.val}</div></div>`
  ).join('');
}

// ── Discover tab ─────────────────────────────────────────────────────────────
function getDiscoverJobs() {
  const q = document.getElementById('discoverSearch').value.toLowerCase();
  const days = parseInt(document.getElementById('discoverDays').value);
  const minScore = parseInt(document.getElementById('discoverScore').value)||0;
  const visa = document.getElementById('discoverVisa').value;
  const now = new Date();
  return allJobs.filter(j => {
    if ((j.status||'new') !== 'new') return false;  // Discover = new only
    if (q && !(j.company||'').toLowerCase().includes(q)
        && !(j.role_title||'').toLowerCase().includes(q)
        && !(j.location||'').toLowerCase().includes(q)) return false;
    if (days > 0) {
      const dateStr = j.posted_date || j.date_found;
      if (dateStr) {
        const age = (now - new Date(dateStr)) / 86400000;
        if (age > days) return false;
      }
    }
    if ((j.match_score||0) < minScore) return false;
    if (visa === 'known' && !(j.visa_sponsor||'').includes('Known')) return false;
    if (activePills.size > 0 && !activePills.has(j.role_category)) return false;
    return true;
  }).sort((a,b) => (b.match_score||0) - (a.match_score||0));
}

function renderDiscover() {
  const jobs = getDiscoverJobs();
  document.getElementById('discoverGrid').innerHTML = jobs.map(renderDiscoverCard).join('');
}

function _scoreBadge(score) {
  if (score >= 80) return ['score-fire', '🔥'];
  if (score >= 60) return ['score-high', '✅'];
  if (score >= 40) return ['score-med', '🟡'];
  return ['score-low', '⚪'];
}

function renderDiscoverCard(j) {
  const score = j.match_score||0;
  const [sc, emoji] = _scoreBadge(score);
  let clusters = '';
  try {
    const cs = typeof j.cluster_scores==='string'?JSON.parse(j.cluster_scores):(j.cluster_scores||{});
    clusters = Object.entries(cs).sort((a,b)=>b[1]-a[1]).slice(0,2).map(([k])=>k.replace(/_/g,' ')).join(', ');
  } catch(e){}
  const jid = j.job_id.replace(/'/g,"\\'");
  const jurl = (j.job_url||'').replace(/'/g,"\\'");
  const mba = j.mba_preferred ? '<div class="mba-badge">🎓 MBA/Master\'s Preferred</div>' : '';
  // Inline contacts for this company
  const compContacts = contacts.filter(c => (c.company||'').toLowerCase() === (j.company||'').toLowerCase());
  const contactHtml = compContacts.length
    ? `<div style="font-size:10px;color:var(--green);margin-top:4px">🤝 ${compContacts.map(c=>esc(c.name)).join(', ')}</div>` : '';
  return `<div class="job-card" onclick="openModal('${jid}')">
    <div class="score-badge ${sc}">${emoji} ${Math.round(score)}</div>
    <div class="jc-company">${esc(j.company)}</div>
    <div class="jc-title">${esc(j.role_title)}</div>
    ${mba}${contactHtml}
    <div class="jc-meta">
      <span>📍 ${j.location||'N/A'}</span>
      <span>${(j.visa_sponsor||'').includes('Known')?'✅':'⚠️'}</span>
      ${j.posted_date?`<span>📅 ${j.posted_date}</span>`:''}
      ${(j.remote||'').includes('🌐')?'<span>🌐 Remote</span>':''}
    </div>
    ${clusters?`<div class="jc-clusters">${clusters}</div>`:''}
    <div class="jc-actions" onclick="event.stopPropagation()">
      ${j.job_url?`<button class="cbtn cbtn-apply" onclick="event.stopPropagation();applyToJob('${jid}','${jurl}')">Apply →</button>`:''}
      <button class="cbtn" style="background:#10B981;color:#fff;border-color:#10B981" onclick="event.stopPropagation();markApplied('${jid}')">✓ Applied</button>
      <button class="cbtn cbtn-save" onclick="event.stopPropagation();saveJob('${jid}')">⭐ Save</button>
      <button class="cbtn cbtn-rebase" onclick="event.stopPropagation();openModal('${jid}')">⚡ Rebase</button>
    </div>
  </div>`;
}

async function applyToJob(jobId, jobUrl) {
  window.open(jobUrl, '_blank');
  await fetch('/api/status', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({job_id:jobId, status:'applying'})
  });
  const j = allJobs.find(x=>x.job_id===jobId);
  if (j) { j.status = 'applying'; j.last_status_change = new Date().toISOString().slice(0,10); }
  showToast('Opened listing — click Mark Applied when done');
  renderDiscover();
  renderPipeline();
}
async function markApplied(jobId) {
  await updateStatus(jobId, 'applied');
  renderDiscover();
  renderPipeline();
}

async function modalMarkApplied(jobId) {
  await updateStatus(jobId, 'applied');
  // Refresh modal to show "Applied" state instead of button
  openModal(jobId);
}

async function saveJob(jobId) {
  await updateStatus(jobId, 'saved');
  renderDiscover();
  renderPipeline();
}

// ── Pipeline tab ─────────────────────────────────────────────────────────────
function getPipelineJobs() {
  return allJobs.filter(j => (j.status||'new') !== 'new');
}

function renderPipeline() {
  const pipelineJobs = getPipelineJobs();
  const board = document.getElementById('kanbanBoard');
  board.innerHTML = PIPELINE_STATUSES.map(status => {
    const jobs = pipelineJobs.filter(j => (j.status||'') === status);
    return `<div class="kanban-col col-${status}" ondragover="event.preventDefault()" ondrop="dropCard(event,'${status}')">
      <div class="col-header">${STATUS_LABELS[status]}<span style="background:rgba(255,255,255,.3);padding:2px 8px;border-radius:10px;font-size:11px">${jobs.length}</span></div>
      <div class="col-body">${jobs.map(j=>renderPipelineCard(j)).join('')}</div>
    </div>`;
  }).join('');

  // Rejected/Withdrawn
  const rejected = pipelineJobs.filter(j => j.status==='rejected'||j.status==='withdrawn');
  document.getElementById('rejectedCount').textContent = `(${rejected.length})`;
  document.getElementById('rejectedCards').innerHTML = rejected.map(j=>renderPipelineCard(j)).join('');
}

function renderPipelineCard(j) {
  const score = j.match_score||0;
  const sc = score>=70?'color:#059669':score>=40?'color:#D97706':'color:#DC2626';
  const jid = j.job_id.replace(/'/g,"\\'");
  const daysSinceStatus = j.last_status_change
    ? Math.round((Date.now() - new Date(j.last_status_change))/86400000)
    : null;
  const appliedDays = j.applied_date
    ? Math.round((Date.now() - new Date(j.applied_date))/86400000)
    : null;
  const mba = j.mba_preferred ? ' 🎓' : '';
  return `<div class="pipeline-card" draggable="true"
    ondragstart="dragCard(event,'${jid}')"
    onclick="openModal('${jid}')">
    <div class="pc-company">${esc(j.company)}</div>
    <div class="pc-title">${esc(j.role_title)}${mba}</div>
    <div class="pc-meta">
      <span style="${sc};font-weight:700">${Math.round(score)}</span>
      ${daysSinceStatus!==null?`<span>${daysSinceStatus}d in status</span>`:''}
      ${appliedDays!==null&&j.status==='applied'?`<span>Applied ${appliedDays}d ago</span>`:''}
    </div>
    ${j.notes?`<div class="pc-notes">${esc(j.notes.slice(0,80))}</div>`:''}
  </div>`;
}

let draggedId = null;
function dragCard(e, id) { draggedId = id; e.dataTransfer.effectAllowed='move'; }
async function dropCard(e, status) {
  e.preventDefault();
  if (!draggedId) return;
  await updateStatus(draggedId, status);
  draggedId = null;
  renderPipeline();
}
function toggleRejected() {
  const el = document.getElementById('rejectedCards');
  const arr = document.getElementById('rejectedArrow');
  const show = el.style.display === 'none';
  el.style.display = show ? 'flex' : 'none';
  arr.textContent = show ? '▼' : '▶';
}

// ── Network tab ──────────────────────────────────────────────────────────────

function buildLinkedInUrls(company, type, roleCategory, jobTitle) {
  const base = 'https://www.linkedin.com/search/results/people/';
  // %22Company%22 for exact-match phrase search on LinkedIn
  const qco = '%22' + encodeURIComponent(company) + '%22';
  // US geography filter (geoUrn 103644278 = United States)
  const geo = '&geoUrn=%5B%22103644278%22%5D';
  const origin = '&origin=GLOBAL_SEARCH_HEADER';

  let kw;
  if (type === 'alumni') {
    kw = qco + '+%22Kelley+School+of+Business%22+OR+%22Indiana+University%22+MBA';
  } else if (type === 'recruiter') {
    const m = {
      'AI/ML Product Manager':    '%22technical+recruiter%22+OR+%22talent+acquisition%22+AI+ML',
      'Product Manager':           '%22technical+recruiter%22+OR+%22talent+acquisition%22+product',
      'Technical Program Manager': '%22technical+recruiter%22+OR+%22talent+acquisition%22+program',
      'Finance & Strategy / FP&A': '%22recruiter%22+OR+%22talent+acquisition%22+finance',
      'Consulting':                '%22recruiter%22+OR+%22talent+partner%22+consulting',
      'Strategy & Operations':     '%22recruiter%22+OR+%22talent+acquisition%22+strategy+operations',
      'Customer Success':          '%22recruiter%22+OR+%22talent+acquisition%22+customer+success',
      'Product Marketing':         '%22recruiter%22+OR+%22talent+acquisition%22+product+marketing',
      'Solutions / Pre-Sales':     '%22recruiter%22+OR+%22talent+acquisition%22+solutions',
    };
    kw = qco + '+' + (m[roleCategory] || '%22recruiter%22+OR+%22talent+acquisition%22');
  } else {
    // same_role: strip seniority prefix and location/classification suffix from title
    let t = (jobTitle || roleCategory || 'product manager').toLowerCase();
    t = t.replace(/^(senior|sr\.?|lead|principal|staff|associate|junior)\s+/i, '');
    t = t.replace(/\s*[-–,|\/]\s*(remote|hybrid|us|usa|sf|nyc|new york|san francisco|austin|seattle).*$/i, '');
    t = t.replace(/\s*\(.*?\)\s*/g, '').trim();
    const skip = new Set(['the','and','for','with','at','in','of','a','an','to','or']);
    const words = t.split(/\s+/).filter(w => w.length > 2 && !skip.has(w)).slice(0, 4);
    kw = qco + '+%22' + encodeURIComponent(words.join(' ')).replace(/%20/g, '+') + '%22';
  }

  return {
    first:  `${base}?keywords=${kw}&network=%5B%22F%22%5D${geo}${origin}`,
    second: `${base}?keywords=${kw}&network=%5B%22S%22%5D${geo}${origin}`,
    third:  `${base}?keywords=${kw}&network=%5B%22O%22%5D${geo}${origin}`,
  };
}

function renderNetwork() {
  const q = (document.getElementById('networkSearch')?.value || '').toLowerCase();
  const companyMap = {};
  for (const j of allJobs) {
    const c = j.company || 'Unknown';
    if (!companyMap[c]) companyMap[c] = [];
    companyMap[c].push(j);
  }
  let sorted = Object.entries(companyMap)
    .map(([co, jobs]) => ({
      company: co,
      bestScore: Math.max(...jobs.map(j => j.match_score || 0)),
      jobCount: jobs.length,
      topJob: [...jobs].sort((a, b) => (b.match_score || 0) - (a.match_score || 0))[0],
    }))
    .sort((a, b) => b.bestScore - a.bestScore || b.jobCount - a.jobCount)
    .slice(0, 40);

  if (q) sorted = sorted.filter(({company}) => company.toLowerCase().includes(q));

  const degRow = (urls, t1, t2, t3) =>
    `<div class="cc-deg-row">
      <a href="${urls.first}"  target="_blank" class="cc-deg cc-deg-1" title="${t1}">🥇 1st°</a>
      <a href="${urls.second}" target="_blank" class="cc-deg cc-deg-2" title="${t2}">🥈 2nd°</a>
      <a href="${urls.third}"  target="_blank" class="cc-deg cc-deg-3" title="${t3}">🥉 3rd°</a>
    </div>`;

  document.getElementById('networkCompanies').innerHTML = sorted.map(({company, bestScore, jobCount, topJob}) => {
    const role = topJob.role_category || '';
    const title = topJob.role_title || '';
    const [sc, emoji] = _scoreBadge(bestScore);
    const jobBadge = jobCount > 1
      ? `<span style="font-size:10px;background:#EEF2FF;color:#4F46E5;padding:2px 7px;border-radius:10px;font-weight:600">${jobCount} roles</span>`
      : '';
    const al = buildLinkedInUrls(company, 'alumni', role, title);
    const re = buildLinkedInUrls(company, 'recruiter', role, title);
    const sr = buildLinkedInUrls(company, 'same_role', role, title);
    const shortRole = role.split('/')[0].trim();
    const shortTitle = title.length > 38 ? title.slice(0, 36) + '…' : title;
    return `<div class="company-card">
      <div class="score-badge ${sc}">${emoji} ${Math.round(bestScore)}</div>
      <div class="cc-name">${esc(company)} ${jobBadge}</div>
      <div class="cc-meta">${esc(role)} · ${esc(title.slice(0, 48))}</div>
      <div class="cc-links">
        <div class="cc-section-label">👩‍🎓 IU/Kelley Alumni at ${esc(company)}</div>
        ${degRow(al, 'Direct connections at ' + company, 'People your connections know at ' + company, 'Extended network at ' + company)}
        <div class="cc-section-label">🎯 Recruiters hiring ${esc(shortRole)}</div>
        ${degRow(re, 'Recruiters you know directly', '2nd-degree recruiters', 'Cold recruiter outreach')}
        <div class="cc-section-label">💼 ${esc(shortTitle)}s</div>
        ${degRow(sr, 'Peers in similar roles (1st°)', 'Peers via shared connections', 'Extended peer network')}
      </div>
    </div>`;
  }).join('') || '<div style="color:var(--muted);padding:20px">No companies match your search.</div>';

  renderCRM();
}

function renderCRM() {
  const q = (document.getElementById('crmSearch2')?.value||'').toLowerCase();
  const relFilter = (document.getElementById('crmRelFilter')?.value||'');
  const filtered = contacts.filter(c =>
    (!q || (c.company||'').toLowerCase().includes(q) || (c.name||'').toLowerCase().includes(q)) &&
    (!relFilter || c.relationship === relFilter)
  );
  const relClass = {cold:'rel-cold',warm:'rel-warm',connected:'rel-connected',replied:'rel-replied'};
  document.getElementById('contactBody').innerHTML = filtered.map(c => `
    <tr>
      <td><strong>${esc(c.name)}</strong></td>
      <td>${esc(c.company)}</td>
      <td>${esc(c.title||'')}</td>
      <td><span class="rel-badge ${relClass[c.relationship]||'rel-cold'}">${c.relationship||'cold'}</span></td>
      <td>${c.last_contacted||'—'}</td>
      <td>${c.next_followup||'—'}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.notes||'')}</td>
      <td>
        <button class="cbtn" onclick="openContactModal(${c.id})">Edit</button>
        <button class="cbtn" onclick="deleteContactRow(${c.id})" style="color:var(--red)">Del</button>
        ${c.linkedin_url?`<a href="${c.linkedin_url}" target="_blank" class="cbtn">LI</a>`:''}
      </td>
    </tr>`).join('');
}

// ── Contact CRUD ─────────────────────────────────────────────────────────────
function openContactModal(id) {
  editingContactId = id;
  const c = id ? contacts.find(x=>x.id===id) : {};
  document.getElementById('contactModalTitle').textContent = id ? 'Edit Contact' : 'Add Contact';
  document.getElementById('contactForm').innerHTML = `
    <div><label style="font-size:11px;color:var(--muted)">Name *</label>
      <input id="cf-name" value="${esc(c?.name||'')}" placeholder="Full name"></div>
    <div><label style="font-size:11px;color:var(--muted)">Company *</label>
      <input id="cf-company" value="${esc(c?.company||'')}" placeholder="Company"></div>
    <div><label style="font-size:11px;color:var(--muted)">Title</label>
      <input id="cf-title" value="${esc(c?.title||'')}" placeholder="Job title"></div>
    <div><label style="font-size:11px;color:var(--muted)">Relationship</label>
      <select id="cf-rel">
        ${['cold','warm','connected','replied'].map(r=>`<option value="${r}"${(c?.relationship||'cold')===r?' selected':''}>${r}</option>`).join('')}
      </select></div>
    <div><label style="font-size:11px;color:var(--muted)">LinkedIn URL</label>
      <input id="cf-li" value="${esc(c?.linkedin_url||'')}" placeholder="https://linkedin.com/in/..."></div>
    <div><label style="font-size:11px;color:var(--muted)">Source</label>
      <select id="cf-src">
        ${['cold','alumni','recruiter','referral','conference'].map(s=>`<option value="${s}"${(c?.source||'cold')===s?' selected':''}>${s}</option>`).join('')}
      </select></div>
    <div><label style="font-size:11px;color:var(--muted)">Last Contacted</label>
      <input id="cf-lc" type="date" value="${c?.last_contacted||''}"></div>
    <div><label style="font-size:11px;color:var(--muted)">Next Follow-up</label>
      <input id="cf-nf" type="date" value="${c?.next_followup||''}"></div>
    <div class="full"><label style="font-size:11px;color:var(--muted)">Notes</label>
      <textarea id="cf-notes" rows="3">${esc(c?.notes||'')}</textarea></div>
  `;
  document.getElementById('contactModalOverlay').classList.add('active');
}
function closeContactModal() {
  document.getElementById('contactModalOverlay').classList.remove('active');
}
async function saveContact() {
  const payload = {
    name: document.getElementById('cf-name').value.trim(),
    company: document.getElementById('cf-company').value.trim(),
    title: document.getElementById('cf-title').value.trim(),
    relationship: document.getElementById('cf-rel').value,
    linkedin_url: document.getElementById('cf-li').value.trim(),
    source: document.getElementById('cf-src').value,
    last_contacted: document.getElementById('cf-lc').value,
    next_followup: document.getElementById('cf-nf').value,
    notes: document.getElementById('cf-notes').value.trim(),
  };
  if (!payload.name || !payload.company) { showToast('Name and Company are required'); return; }
  if (editingContactId) {
    await fetch(`/api/contacts/${editingContactId}`, {
      method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
  } else {
    await fetch('/api/contacts', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
  }
  closeContactModal();
  const res = await fetch('/api/contacts');
  contacts = await res.json();
  renderCRM();
  showToast(editingContactId ? 'Contact updated' : 'Contact added');
}
async function deleteContactRow(id) {
  if (!confirm('Delete this contact?')) return;
  await fetch(`/api/contacts/${id}`, {method:'DELETE'});
  contacts = contacts.filter(c=>c.id!==id);
  renderCRM();
  showToast('Contact deleted');
}

// ── Job detail modal ──────────────────────────────────────────────────────────
function openModal(jobId) {
  const j = allJobs.find(x=>x.job_id===jobId);
  if (!j) return;
  let clusters = {};
  try { clusters = typeof j.cluster_scores==='string'?JSON.parse(j.cluster_scores):(j.cluster_scores||{}); } catch(e){}
  const topClusters = Object.entries(clusters).sort((a,b)=>b[1]-a[1]).slice(0,5);
  const jid = j.job_id.replace(/'/g,"\\'");
  const jurl = (j.job_url||'').replace(/'/g,"\\'");

  const clusterHtml = topClusters.length ? `
    <div style="margin:16px 0">
      <div style="font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:.05em;margin-bottom:8px">Keyword Match</div>
      ${topClusters.map(([k,v])=>`
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
          <span style="font-size:12px;width:140px">${k.replace(/_/g,' ')}</span>
          <div style="flex:1;height:7px;background:#E5E7EB;border-radius:3px;overflow:hidden">
            <div style="width:${Math.min(v,100)}%;height:100%;background:${v>=50?'#059669':v>=25?'#D97706':'#DC2626'};border-radius:3px"></div>
          </div>
          <span style="font-size:11px;color:var(--muted)">${Math.round(v)}%</span>
        </div>`).join('')}
    </div>` : '';

  const mbaTag = j.mba_preferred ? '<span style="background:#FFF8E1;color:#7D5A00;border:1px solid #FDD835;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600">🎓 MBA/Master\'s Preferred</span>' : '';
  const scoreColor = (j.match_score||0)>=70?'#059669':(j.match_score||0)>=40?'#D97706':'#DC2626';

  document.getElementById('jobModal').innerHTML = `
    <h2>${esc(j.role_title)}</h2>
    <div class="mc">${esc(j.company)} · ${j.ats_source||''} · ${j.posted_date||''}</div>
    ${mbaTag ? `<div style="margin-bottom:12px">${mbaTag}</div>` : ''}
    <div class="modal-grid">
      <div class="mf"><div class="lbl">Score</div><div class="val" style="font-size:20px;color:${scoreColor}">${Math.round(j.match_score||0)}/100</div></div>
      <div class="mf"><div class="lbl">Location</div><div class="val">${j.location||'N/A'}${(j.remote||'').includes('🌐')?' (Remote)':''}</div></div>
      <div class="mf"><div class="lbl">Visa</div><div class="val">${j.visa_sponsor||'N/A'}</div></div>
      <div class="mf"><div class="lbl">Status</div><div class="val">
        <select class="status-sel" onchange="updateStatus('${jid}',this.value)">
          ${['new','saved','applying','applied','interviewing','offer','rejected','withdrawn'].map(s=>`<option value="${s}"${(j.status||'new')===s?' selected':''}>${STATUS_LABELS[s]||s}</option>`).join('')}
        </select>
      </div></div>
    </div>
    ${clusterHtml}
    <div style="margin-top:14px">
      <div style="font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:.05em;margin-bottom:6px">Notes</div>
      <textarea id="modalNotes" placeholder="Add notes…" onblur="autoSaveNotes('${jid}')">${j.notes||''}</textarea>
    </div>
    <div class="modal-actions">
      ${j.job_url?`<button class="cbtn cbtn-apply" style="padding:8px 18px;font-size:13px" onclick="applyToJob('${jid}','${jurl}')">Open Listing →</button>`:''}
      ${(j.status||'new') !== 'applied' ? `<button class="cbtn" style="background:#059669;color:#fff;border-color:#059669;padding:8px 18px;font-size:13px" onclick="modalMarkApplied('${jid}')">✅ Mark Applied</button>` : '<span style="color:#059669;font-size:13px;font-weight:600;padding:8px 0">✅ Applied '+(j.applied_date||'')+'</span>'}
      <button class="cbtn cbtn-rebase" style="padding:8px 18px;font-size:13px" onclick="triggerRebase('${jid}')">⚡ Generate Tailored Resume</button>
      <button class="cbtn" style="padding:8px 18px;font-size:13px" onclick="closeModal()">Close</button>
    </div>
    <div class="rebase-out" id="rebaseOut"></div>`;

  document.getElementById('jobModalOverlay').classList.add('active');
}
function closeModal() { document.getElementById('jobModalOverlay').classList.remove('active'); }

async function autoSaveNotes(jobId) {
  const notes = document.getElementById('modalNotes')?.value;
  if (notes === undefined) return;
  await fetch('/api/notes', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({job_id:jobId, notes})
  });
  const j = allJobs.find(x=>x.job_id===jobId);
  if (j) j.notes = notes;
}

async function triggerRebase(jobId) {
  const out = document.getElementById('rebaseOut');
  out.style.display = 'block';
  out.textContent = '⏳ Generating tailored resume prompt…';
  try {
    const res = await fetch('/api/rebase', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({job_id:jobId})
    });
    const data = await res.json();
    if (data.error) { out.textContent = '❌ ' + data.error; return; }
    out.innerHTML = `<div style="margin-bottom:10px"><strong>✅ Ready — Tier: ${esc(data.tier)}</strong></div>
      <div style="background:#fff;border:1px solid var(--border);border-radius:8px;padding:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:11px;color:var(--muted)">REBASE PROMPT</span>
          <button class="cbtn" onclick="copyRebase()">📋 Copy</button>
        </div>
        <pre id="rebaseText" style="white-space:pre-wrap;font-size:12px;line-height:1.5">${esc(data.rebase_prompt)}</pre>
      </div>
      ${data.cluster_info?`<div style="margin-top:8px;font-size:11px;color:var(--muted)">${esc(data.cluster_info)}</div>`:''}`;
  } catch(e) { out.textContent = '❌ Error: ' + e.message; }
}
function copyRebase() {
  const el = document.getElementById('rebaseText');
  if (el) { navigator.clipboard.writeText(el.textContent); showToast('Copied to clipboard'); }
}

// ── Shared helpers ────────────────────────────────────────────────────────────
async function updateStatus(jobId, status) {
  await fetch('/api/status', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({job_id:jobId, status})
  });
  const j = allJobs.find(x=>x.job_id===jobId);
  if (j) {
    j.status = status;
    j.last_status_change = new Date().toISOString().slice(0,10);
    if (status === 'applied') j.applied_date = new Date().toISOString().slice(0,10);
  }
  showToast('Moved to ' + (STATUS_LABELS[status]||status));
  renderDiscover();
  renderPipeline();
}

function togglePill(el) {
  const cat = el.dataset.cat;
  if (activePills.has(cat)) { activePills.delete(cat); el.classList.remove('active'); }
  else { activePills.add(cat); el.classList.add('active'); }
  renderDiscover();
}

function setTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
  if (name==='network') renderNetwork();
  if (name==='outreach') renderCRM();
}

async function runFeed() {
  showToast('🔄 Fetching jobs… ~10s');
  const res = await fetch('/api/run', {method:'POST'});
  const data = await res.json();
  showToast(`✅ ${data.new_jobs||0} new jobs found`);
  await loadAll();
}

function exportExcel() {
  showToast('📊 Generating Excel…');
  window.open('/api/export','_blank');
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 3200);
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s||'';
  return d.innerHTML;
}

loadAll();
</script>
</body>
</html>"""

# ─── API ROUTES ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/jobs")
def api_jobs():
    days = request.args.get("days", 30, type=int)
    jobs = get_jobs(days=days, limit=2000)
    return jsonify(jobs)


@app.route("/api/stats")
def api_stats():
    stats = get_stats(days=7)
    conn = get_connection()
    high = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE date_found >= date('now', '-7 days') "
        "AND match_score >= 70"
    ).fetchone()[0]
    conn.close()
    stats["high_fit"] = high
    return jsonify(stats)


@app.route("/api/status", methods=["POST"])
def api_status():
    data = request.json
    update_job_status(
        data["job_id"], data["status"],
        notes=data.get("notes"),
        resume_version=data.get("resume_version"),
    )
    return jsonify({"ok": True})


@app.route("/api/notes", methods=["POST"])
def api_notes():
    data = request.json
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET notes = ?, updated_at = datetime('now') WHERE job_id = ?",
        (data["notes"], data["job_id"])
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/rebase", methods=["POST"])
def api_rebase():
    data = request.json
    job_id = data["job_id"]
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Job not found"})
    job = dict(row)
    description = job.get("description") or ""

    if len(description) < 200 and job.get("job_url"):
        try:
            import requests as req, re
            r = req.get(job["job_url"], timeout=10,
                       headers={"User-Agent": "Mozilla/5.0"})
            if r.ok:
                text = re.sub(r'<[^>]+>', ' ', r.text)
                text = re.sub(r'\s+', ' ', text).strip()
                description = text[:8000]
                c2 = get_connection()
                c2.execute("UPDATE jobs SET description = ? WHERE job_id = ?",
                           (description, job_id))
                c2.commit()
                c2.close()
        except Exception:
            pass

    score = job.get("match_score") or 0
    tier = "full" if score >= 85 else "target" if score >= 70 else "bulk"

    prompt = (f"{tier}:\n\n"
              f"{job.get('company', '')} — {job.get('role_title', '')}\n"
              f"{job.get('job_url', '')}\n\n"
              f"{description if description else '[Paste full JD here]'}")

    cluster_info = ""
    try:
        cs = json.loads(job.get("cluster_scores") or "{}")
        top = sorted(cs.items(), key=lambda x: x[1], reverse=True)[:5]
        if top:
            cluster_info = "Top matching clusters: " + ", ".join(
                f"{k.replace('_',' ')} ({v:.0f}%)" for k, v in top
            )
    except Exception:
        pass

    return jsonify({"rebase_prompt": prompt, "cluster_info": cluster_info, "tier": tier})


@app.route("/api/run", methods=["POST"])
def api_run():
    try:
        import re as _re
        result = subprocess.run(
            [sys.executable, os.path.join(FEED_DIR, "job_feed.py")],
            capture_output=True, text=True, timeout=180, cwd=FEED_DIR,
        )
        match = _re.search(r"New: (\d+)", result.stdout)
        new_count = int(match.group(1)) if match else 0
        return jsonify({"ok": True, "new_jobs": new_count,
                       "output": result.stdout[-500:]})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/export")
def api_export():
    from build_excel_v3 import build_excel
    jobs = get_jobs(days=7, limit=2000)
    contacts_data = get_contacts()
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"job_feed_{today}.xlsx")
    build_excel(jobs, path, contacts=contacts_data)
    return send_file(path, as_attachment=True)


# ─── NETWORK API ──────────────────────────────────────────────────────────────

@app.route("/api/network")
def api_network():
    """Return companies ranked by fit score with pre-built LinkedIn search URLs."""
    jobs = get_jobs(days=30, limit=2000)

    companies = {}
    for j in jobs:
        co = j.get("company", "")
        if not co:
            continue
        if co not in companies:
            companies[co] = {"company": co, "job_count": 0, "best_score": 0,
                             "best_title": "", "best_category": "", "categories": set()}
        companies[co]["job_count"] += 1
        companies[co]["categories"].add(j.get("role_category", ""))
        score = float(j.get("match_score", 0) or 0)
        if score > companies[co]["best_score"]:
            companies[co]["best_score"] = score
            companies[co]["best_title"] = j.get("role_title", "")
            companies[co]["best_category"] = j.get("role_category", "")

    result = []
    for co, data in companies.items():
        primary_cat = data["best_category"] or "Product Manager"
        result.append({
            "company": co,
            "job_count": data["job_count"],
            "best_score": round(data["best_score"], 1),
            "best_title": data["best_title"],
            "best_category": primary_cat,
            "categories": list(data["categories"]),
            "alumni_urls":   build_linkedin_urls(co, "alumni"),
            "recruiter_urls": build_linkedin_urls(co, "hiring_team", role_category=primary_cat),
            "same_role_urls": build_linkedin_urls(co, "same_role",
                                                  role_category=primary_cat,
                                                  job_title=data["best_title"]),
        })

    result.sort(key=lambda x: (x["best_score"], x["job_count"]), reverse=True)
    return jsonify(result)


# ─── CONTACTS API ─────────────────────────────────────────────────────────────

@app.route("/api/contacts")
def api_contacts():
    company = request.args.get("company")
    return jsonify(get_contacts(company=company))


@app.route("/api/contacts", methods=["POST"])
def api_contacts_create():
    data = request.json
    new_id = insert_contact(data)
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/contacts/<int:contact_id>", methods=["PUT"])
def api_contacts_update(contact_id):
    data = request.json
    update_contact(contact_id, data)
    return jsonify({"ok": True})


@app.route("/api/contacts/<int:contact_id>", methods=["DELETE"])
def api_contacts_delete(contact_id):
    delete_contact(contact_id)
    return jsonify({"ok": True})


# ─── TOUCHPOINTS API ──────────────────────────────────────────────────────────

@app.route("/api/contacts/<int:contact_id>/touchpoints", methods=["GET"])
def api_get_touchpoints(contact_id):
    return jsonify(get_touchpoints(contact_id))


@app.route("/api/contacts/<int:contact_id>/touchpoints", methods=["POST"])
def api_log_touchpoint(contact_id):
    data = request.json
    new_id = log_touchpoint(
        contact_id,
        channel=data.get("channel", "email"),
        direction=data.get("direction", "outbound"),
        subject=data.get("subject"),
        notes=data.get("notes"),
    )
    return jsonify({"ok": True, "id": new_id})


# ─── ENRICHMENT API ───────────────────────────────────────────────────────────

@app.route("/api/contacts/<int:contact_id>/enrich", methods=["POST"])
def api_enrich_contact(contact_id):
    try:
        from enrichment import get_provider
        data = request.json or {}
        provider = get_provider(data.get("provider"))
        # Load current contact data to pass identifiers
        conn = get_connection()
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Contact not found"}), 404
        c = dict(row)
        result = provider.enrich(
            email=c.get("email"),
            name=c.get("name"),
            company=c.get("company"),
            linkedin_url=c.get("linkedin_url"),
        )
        apply_enrichment(contact_id, result)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── SETTINGS API ─────────────────────────────────────────────────────────────

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    if os.path.exists(SETTINGS_PATH):
        try:
            import json as _json
            data = _json.loads(open(SETTINGS_PATH).read())
            # Mask API keys
            masked = {}
            for k, v in data.items():
                masked[k] = "***" + str(v)[-4:] if "key" in k.lower() and v else v
            return jsonify(masked)
        except Exception:
            pass
    return jsonify({})


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    import json as _json
    data = request.json or {}
    # Load existing settings to merge (don't overwrite masked values)
    existing = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            existing = _json.loads(open(SETTINGS_PATH).read())
        except Exception:
            pass
    for k, v in data.items():
        if v and not str(v).startswith("***"):   # don't write back masked values
            existing[k] = v
    with open(SETTINGS_PATH, "w") as f:
        _json.dump(existing, f, indent=2)
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    print("\n🚀 Job Feed Dashboard")
    print("   http://localhost:5050")
    print("   Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=5050, debug=False)
