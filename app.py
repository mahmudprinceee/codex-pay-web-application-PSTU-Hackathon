import os
import uuid
import html
import base64
import pandas as pd
import requests
import streamlit as st

API = "http://127.0.0.1:8000"

# Premium Codex Pay mark — a card/wallet glyph with a small gold sparkle,
# used everywhere the brand mark appears (auth hero, sidebar). Kept as one
# constant so the mark stays identical wherever it's reused.
CODEX_LOGO_SVG = (
    "<svg viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg' "
    "style='width:58%;height:58%;display:block;margin:auto'>"
    "<rect x='3' y='10' width='34' height='24' rx='7' fill='#ffffff'/>"
    "<rect x='3' y='10' width='34' height='8' rx='4' fill='#ffffff' fill-opacity='.55'/>"
    "<circle cx='28.5' cy='24' r='4.2' fill='#7B1FA2'/>"
    "<path d='M8 10V8.3A5.3 5.3 0 0 1 13.3 3H24' stroke='#ffffff' "
    "stroke-width='2.4' stroke-linecap='round' fill='none'/>"
    "<path d='M34.3 2.6l1.05 2.35 2.35 1.05-2.35 1.05-1.05 2.35-1.05-2.35"
    "-2.35-1.05 2.35-1.05z' fill='#FFD54F'/>"
    "</svg>"
)

def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

st.set_page_config(
    page_title="Codex Pay",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Design ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root{
    --pink:#E91E63;
    --pink-dark:#C2185B;
    --purple:#7B1FA2;
    --orange:#FF6D00;
    --ink:#17203A;
    --muted:#5B6578;
    --bg:#f7f8fb;
    --bg-light:#FAF8FC;
    --white:#ffffff;
    --line:#e9ebf0;
    --green:#149447;
    --green-bg:#eaf8f0;
    --red:#c93636;
}

html,body,[class*="css"],.stApp{
    font-family:'Plus Jakarta Sans',Arial,sans-serif !important;
    color:var(--ink) !important;
}
.stApp{background:var(--bg);}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stSidebar"]{display:none;}
.block-container{
    max-width:1520px;
    padding:0 !important;
}
h1,h2,h3,h4,p,span,label,button,input,textarea,div{
    font-family:'Plus Jakarta Sans',Arial,sans-serif !important;
}
h1,h2,h3,h4{color:var(--ink) !important;}

/* ==================================================
   Dashboard shell: fixed left sidebar + scrollable main
   ================================================== */
/* NOTE: st.markdown() renders each call as its own isolated HTML
   fragment, so a <div> opened in one st.markdown call and "closed" in
   a later call never actually wraps the Streamlit elements emitted in
   between — it just becomes an empty, self-closed div, and any height/
   layout rule on it (e.g. min-height) still applies to that EMPTY div,
   which silently pushes real content off-screen. To style Streamlit's
   real column containers we drop an invisible marker div as the first
   element inside each column and target the column with :has(), which
   DOES see genuine descendants since `with col:` gives real DOM
   nesting (unlike chained st.markdown calls). Same idea, using the
   adjacent-sibling combinator, is used below for individual buttons.
*/
[data-testid="stColumn"]:has(.sidebar-marker){
    background:#fff;border-right:1px solid var(--line);
    position:sticky;top:0;height:100vh;overflow-y:auto;
    padding:26px 20px 20px;
}
.sidebar-brand{padding:4px 6px 22px;}
.sidebar-logo-badge{
    width:46px;height:46px;border-radius:14px;
    background:linear-gradient(135deg,#E91E63,#7B1FA2);
    display:flex;align-items:center;justify-content:center;
    font-size:20px;color:#fff;font-weight:800;margin-bottom:10px;
    box-shadow:0 8px 18px rgba(123,31,162,.25);
}
.sidebar-wordmark{font-size:21px;font-weight:900;letter-spacing:.2px;}
.sidebar-wordmark .navy{color:var(--ink);}
.sidebar-wordmark .pink{color:var(--pink);}
.sidebar-tagline{font-size:12px;color:var(--muted);font-weight:600;margin-top:2px;}

[data-testid="stElementContainer"]:has(.side-nav-marker) + [data-testid="stElementContainer"] .stButton>button{
    display:flex !important;justify-content:flex-start !important;gap:10px !important;
    border:1px solid transparent !important;background:transparent !important;
    color:var(--ink) !important;font-weight:700 !important;font-size:14.5px !important;
    min-height:46px !important;border-radius:13px !important;padding:0 14px !important;
    box-shadow:none !important;margin-bottom:3px !important;text-align:left !important;
}
[data-testid="stElementContainer"]:has(.side-nav-marker) + [data-testid="stElementContainer"] .stButton>button:hover{
    background:#fdf0f6 !important;color:var(--pink) !important;
}
[data-testid="stElementContainer"]:has(.side-nav-marker.active) + [data-testid="stElementContainer"] .stButton>button{
    background:linear-gradient(135deg,#E91E63,#8E24AA) !important;color:#fff !important;
    box-shadow:0 10px 22px rgba(190,30,120,.25) !important;
}
.sidebar-promo{
    border-radius:18px;padding:16px 16px 15px;margin-top:10px;color:#fff;
    background:linear-gradient(135deg,#EC1473 0%,#8E24AA 100%);
    box-shadow:0 10px 24px rgba(180,30,130,.18);
}
.sidebar-promo.support{
    background:linear-gradient(135deg,#FFB347 0%,#FF7A59 100%);
    box-shadow:0 10px 24px rgba(255,130,60,.18);
}
.sidebar-promo-title{font-weight:800;font-size:13.5px;margin:6px 0 2px;}
.sidebar-promo-sub{font-size:11.5px;opacity:.94;line-height:1.5;font-weight:500;}

[data-testid="stColumn"]:has(.main-marker){padding:26px 32px 60px;}


/* ---- Top header ---- */
.top-row{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:22px;}
.hello{font-size:27px;font-weight:800;line-height:1.15;color:var(--ink);}
.uid{font-size:14px;color:var(--muted);margin-top:6px;font-weight:500;}
.top-actions{display:flex;gap:12px;align-items:center;}
.bell-dot{
    position:relative;width:44px;height:44px;border-radius:50%;background:#fff;
    border:1px solid var(--line);display:flex;align-items:center;justify-content:center;
    font-size:19px;box-shadow:0 5px 16px rgba(20,30,50,.07);
}
.bell-dot .badge{
    position:absolute;top:-4px;right:-4px;background:var(--pink);color:#fff;
    font-size:10.5px;font-weight:800;border-radius:999px;
    min-width:18px;height:18px;display:flex;align-items:center;justify-content:center;
    border:2px solid #fff;
}
.avatar-dot{
    width:44px;height:44px;border-radius:50%;
    background:linear-gradient(135deg,#E91E63,#7B1FA2);
    display:flex;align-items:center;justify-content:center;color:#fff;font-size:19px;
    box-shadow:0 6px 16px rgba(123,31,162,.25);
}

/* ---- Balance + debit card ---- */
.balance{
    min-height:210px;
    padding:26px 28px;
    border-radius:22px;
    color:white;
    position:relative;
    overflow:hidden;
    background:
    radial-gradient(
        circle at 82% 18%,
        rgba(139,92,246,.20) 0%,
        transparent 30%
    ),
    radial-gradient(
        circle at 15% 85%,
        rgba(37,99,235,.12) 0%,
        transparent 32%
    ),
    linear-gradient(
        135deg,
        #020106 0%,
        #070512 28%,
        #110A20 52%,
        #1C1033 76%,
        #32145A 100%
    );
   box-shadow:
    0 24px 55px rgba(0,0,0,.52),
    0 10px 28px rgba(50,20,90,.22),
    inset 0 1px 0 rgba(255,255,255,.16),
    inset 0 -1px 0 rgba(0,0,0,.35);
}
}
box-shadow:
    0 24px 55px rgba(0,0,0,.52),
    0 10px 28px rgba(50,20,90,.22),
    inset 0 1px 0 rgba(255,255,255,.16),
    inset 0 -1px 0 rgba(0,0,0,.35);
.balance:after{
    content:"";position:absolute;width:220px;height:220px;right:-70px;bottom:-110px;
    border-radius:50%;background:rgba(255,255,255,.08);
}
.balance-top{display:flex;justify-content:space-between;align-items:flex-start;position:relative;z-index:2;}
.balance-label{font-size:15px;font-weight:600;opacity:.96;}
.balance-eye{font-size:19px;opacity:.9;}
.balance-amount{font-size:38px;font-weight:800;letter-spacing:-1px;margin:10px 0 16px;position:relative;z-index:2;}
.status-line{font-size:14px;font-weight:600;position:relative;z-index:2;}
.status-pill{
    display:inline-block;margin-left:8px;padding:4px 11px;border-radius:999px;
    background:#19a95c;color:#fff;font-size:11.5px;font-weight:800;
}

.debit-card{
    height:260px;
    min-height:260px;
    padding:18px 24px;
    border-radius:18px;
    position:relative;
    overflow:hidden;
    box-sizing:border-box;

    background:
        radial-gradient(
            circle at 90% 15%,
            rgba(96,165,250,.22),
            transparent 30%
        ),
        linear-gradient(
            135deg,
            #020617 0%,
            #0b1733 38%,
            #142b52 70%,
            #1e3a5f 100%
        );

    border:1px solid rgba(148,163,184,.28);

    color:#ffffff;

    box-shadow:
        0 20px 45px rgba(2,6,23,.45),
        0 5px 18px rgba(59,130,246,.16);
}

.debit-card *{
    color:#ffffff !important;
}

.debit-card .debit-head{
    margin-bottom:8px !important;
}

.debit-card .debit-number{
    margin:8px 0 !important;
    line-height:1.2 !important;
    letter-spacing:2px;
}

.debit-card .debit-holder{
    margin-top:6px !important;
    line-height:1.2 !important;
}

.debit-card .debit-account{
    margin-top:2px !important;
    line-height:1.2 !important;
}

.debit-card .debit-valid{
    margin-top:2px !important;
    line-height:1.2 !important;
}

.debit-card > *{
    position:relative;
    z-index:2;
}

.debit-card::before{
    content:"";
    position:absolute;
    width:300px;
    height:300px;
    right:-130px;
    top:-150px;
    border-radius:50%;
    border:1px solid rgba(148,163,184,.14);
    box-shadow:
        0 0 0 35px rgba(148,163,184,.04),
        0 0 0 70px rgba(148,163,184,.03);
    pointer-events:none;
    z-index:1;
}

.debit-card::after{
    content:"";
    position:absolute;
    width:180px;
    height:180px;
    left:-90px;
    bottom:-110px;
    border-radius:50%;
    background:rgba(37,99,235,.14);
    pointer-events:none;
    z-index:1;
}
.debit-card:after{
    content:"";position:absolute;right:-40px;top:-40px;width:230px;height:230px;
    background:radial-gradient(circle,rgba(212,175,90,.14) 0%,rgba(212,175,90,0) 70%);
    border-radius:50%;
}
.debit-head{display:flex;justify-content:space-between;align-items:flex-start;position:relative;z-index:2;}
.debit-bank-icon{
    width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.1);
    display:flex;align-items:center;justify-content:center;font-size:17px;margin-bottom:6px;
}
.debit-bank-name{font-size:16.5px;font-weight:800;}
.debit-bank-sub{font-size:12px;color:#aab4c8;margin-top:1px;}
.debit-type{font-size:11.5px;letter-spacing:1.5px;color:#c9d2e3;font-weight:700;}
.debit-chip-row{display:flex;align-items:center;gap:10px;margin-top:20px;position:relative;z-index:2;}
.debit-chip{
    width:38px;height:28px;border-radius:6px;
    background:linear-gradient(135deg,#f0c45c,#c99a2f);
}
.debit-wave{font-size:18px;color:#c9d2e3;}
.debit-number{
    font-size:20px;letter-spacing:3px;font-weight:600;margin-top:20px;
    position:relative;z-index:2;font-family:'Inter',monospace;
}
.debit-foot{display:flex;justify-content:space-between;align-items:flex-end;margin-top:18px;position:relative;z-index:2;}
.debit-name{font-size:14.5px;font-weight:700;letter-spacing:.5px;}
.debit-acct{font-size:11px;color:#aab4c8;margin-top:4px;}
.debit-valid{font-size:10.5px;color:#aab4c8;text-align:right;}
.debit-valid b{color:#fff;font-size:12px;display:block;}
.debit-visa{font-size:22px;font-weight:900;font-style:italic;letter-spacing:.5px;}

/* ---- Section titles ---- */
.section-title{font-size:19px;font-weight:800;margin:26px 0 14px;}
.section-link{float:right;color:var(--pink);font-size:13.5px;font-weight:700;}

/* ---- Quick action cards ---- */
.quick-card{
    background:#fff;border:1px solid var(--line);border-radius:18px;
    padding:18px 18px 16px;box-shadow:0 6px 20px rgba(20,30,50,.045);
}
.quick-icon{
    width:44px;height:44px;border-radius:13px;display:flex;align-items:center;justify-content:center;
    font-size:20px;margin-bottom:10px;
}
.quick-title{font-size:14.5px;font-weight:800;color:var(--ink);}
.quick-sub{font-size:12px;color:var(--muted);margin-top:2px;margin-bottom:12px;}

/* ---- Service grid tiles ---- */
.service-tile{
    background:#fff;border:1px solid var(--line);border-radius:16px;
    padding:16px 16px 12px;box-shadow:0 5px 18px rgba(20,30,50,.04);
}
.service-icon{
    width:38px;height:38px;border-radius:11px;margin-bottom:8px;
    display:flex;align-items:center;justify-content:center;font-size:18px;
}
.service-name{font-size:13.5px;font-weight:800;color:var(--ink);}
.service-sub{font-size:11px;color:var(--muted);margin-top:2px;margin-bottom:10px;}

.tx-card{
    background:#fff;border:1px solid var(--line);border-radius:17px;
    overflow:hidden;box-shadow:0 6px 20px rgba(20,30,50,.04);
}
.tx-row{
    display:flex;align-items:center;justify-content:space-between;
    padding:15px 18px;border-bottom:1px solid #f0f1f4;
}
.tx-row:last-child{border-bottom:0;}
.tx-left{display:flex;gap:12px;align-items:center;}
.tx-icon{
    width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-weight:800;background:#fff0f7;color:var(--pink);
}
.tx-name{font-weight:750;font-size:14px;}
.tx-desc{font-size:12px;color:var(--muted);margin-top:3px;}
.tx-right{text-align:right;}
.tx-amount{font-weight:800;color:var(--pink);font-size:14px;}
.tx-time{font-size:12px;color:var(--muted);margin-top:3px;}

.req-card{
    background:#fff;border:1px solid var(--line);border-radius:17px;
    overflow:hidden;box-shadow:0 6px 20px rgba(20,30,50,.04);margin-bottom:16px;
}
.req-row{
    display:flex;align-items:center;justify-content:space-between;
    padding:16px 18px;border-bottom:1px solid #f0f1f4;gap:14px;
}
.req-row:last-child{border-bottom:0;}
.req-left{display:flex;gap:12px;align-items:center;}
.req-icon{
    width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-size:18px;background:#fff6df;
}
.req-name{font-weight:750;font-size:14px;}
.req-desc{font-size:12px;color:var(--muted);margin-top:3px;}
.req-amount{font-weight:800;font-size:15px;color:var(--ink);white-space:nowrap;}
.req-status-pill{
    display:inline-block;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:800;
}
.req-status-pending{background:#fff6df;color:#a56b00;}
.req-status-completed{background:var(--green-bg);color:var(--green);}
.req-status-rejected{background:#fff0f1;color:var(--red);}

.form-shell{
    background:#fff;border:1px solid var(--line);border-radius:22px;
    padding:25px;box-shadow:0 9px 26px rgba(20,30,50,.05);
}
.form-title{font-size:25px;font-weight:800;color:var(--ink);}
.form-sub{color:var(--muted);font-size:14px;margin:5px 0 18px;}

.success-box{
    background:var(--green-bg);border:1px solid #bde8cf;color:var(--green);
    border-radius:14px;padding:15px;font-weight:800;
}
.error-box{
    background:#fff0f1;border:1px solid #f0c7cb;color:var(--red);
    border-radius:14px;padding:14px;font-weight:700;
}

/* ---- Bottom trust strip ---- */
.trust-strip{
    display:flex;flex-wrap:wrap;justify-content:space-between;gap:14px 22px;
    background:#fff;border:1px solid var(--line);border-radius:18px;
    padding:16px 22px;margin-top:30px;box-shadow:0 6px 20px rgba(20,30,50,.04);
}
.trust-strip-item{display:flex;gap:10px;align-items:center;}
.trust-strip-ico{
    width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-size:15px;color:#fff;flex:none;
}
.trust-strip-title{font-size:13px;font-weight:800;color:var(--ink);}
.trust-strip-sub{font-size:11px;color:var(--muted);margin-top:1px;}

.stButton>button{
    border-radius:13px !important;
    min-height:44px !important;
    font-weight:700 !important;
    border:1px solid var(--line) !important;
    background:#fff !important;
    color:var(--ink) !important;
    box-shadow:none !important;
}
.stButton>button:hover{
    border-color:#f1a3c5 !important;
    color:var(--pink) !important;
}
.primary-btn .stButton>button{
    background:var(--pink) !important;color:#fff !important;border-color:var(--pink) !important;
}
[data-testid="stElementContainer"]:has(.quick-send-marker) + [data-testid="stElementContainer"] .stButton>button{background:linear-gradient(135deg,#E91E63,#C2185B) !important;color:#fff !important;border:none !important;}
[data-testid="stElementContainer"]:has(.quick-recharge-marker) + [data-testid="stElementContainer"] .stButton>button{background:linear-gradient(135deg,#8E24AA,#5E1A8A) !important;color:#fff !important;border:none !important;}
[data-testid="stElementContainer"]:has(.quick-cashout-marker) + [data-testid="stElementContainer"] .stButton>button{background:linear-gradient(135deg,#FF7A3C,#E8481C) !important;color:#fff !important;border:none !important;}
[data-testid="stElementContainer"]:has(.quick-paybill-marker) + [data-testid="stElementContainer"] .stButton>button{background:linear-gradient(135deg,#12B886,#0B8F68) !important;color:#fff !important;border:none !important;}
[data-testid="stElementContainer"]:has(.quick-send-marker) + [data-testid="stElementContainer"] .stButton>button:hover,
[data-testid="stElementContainer"]:has(.quick-recharge-marker) + [data-testid="stElementContainer"] .stButton>button:hover,
[data-testid="stElementContainer"]:has(.quick-cashout-marker) + [data-testid="stElementContainer"] .stButton>button:hover,
[data-testid="stElementContainer"]:has(.quick-paybill-marker) + [data-testid="stElementContainer"] .stButton>button:hover{opacity:.92;color:#fff !important;}
.service-button .stButton>button{
    background:#fff !important;color:var(--ink) !important;
    border-color:var(--line) !important;font-weight:700 !important;
}
.service-button .stButton>button:hover{
    background:#fff7fa !important;border-color:#f0a3c5 !important;
}
[data-testid="stElementContainer"]:has(.accept-btn-marker) + [data-testid="stElementContainer"] .stButton>button{background:var(--green) !important;color:#fff !important;border-color:var(--green) !important;}
[data-testid="stElementContainer"]:has(.reject-btn-marker) + [data-testid="stElementContainer"] .stButton>button{background:#fff !important;color:var(--red) !important;border-color:#f0c7cb !important;}
.logout .stButton>button{background:#172033 !important;color:#fff !important;border-color:#172033 !important;}

/* ---- Form readability fix ---- */
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stTextArea"] label,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label{
    color:var(--ink) !important;
    font-weight:700 !important;
    opacity:1 !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea{
    border-radius:12px !important;
    border:1px solid #cfd5df !important;
    color:var(--ink) !important;
    background:#fff !important;
    -webkit-text-fill-color:var(--ink) !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{
    color:#8a93a3 !important;opacity:1 !important;
}
/* Streamlit's built-in show/hide-password button renders a Material
   Symbols ligature ("visibility"/"visibility_off"); when that icon font
   fails to load it falls back to showing that literal word instead of an
   eye icon. The button itself already works (it toggles the field's
   type) — we just swap what's drawn on it for a real eye emoji, right
   where the broken text was, instead of adding a separate button. */
[data-testid="stTextInputRevealButton"]{
    position:relative !important;color:transparent !important;
}
[data-testid="stTextInputRevealButton"] *{
    font-size:0 !important;line-height:0 !important;color:transparent !important;
}
[data-testid="stTextInputRevealButton"]::after{
    content:"👁";position:absolute;top:50%;left:50%;
    transform:translate(-50%,-50%);font-size:17px;line-height:1;
}
[data-testid="stTextInputRevealButton"][aria-label="Hide password text"]::after{
    content:"🙈";
}
[data-testid="stElementContainer"]:has(.eye-btn-marker) + [data-testid="stElementContainer"] .stButton>button{
    background:#fff !important;border:1px solid #cfd5df !important;border-radius:12px !important;
    color:var(--ink) !important;font-size:16px !important;padding:0 !important;
    min-height:44px !important;box-shadow:none !important;
}
[data-testid="stElementContainer"]:has(.eye-btn-marker) + [data-testid="stElementContainer"] .stButton>button:hover{
    border-color:var(--pink) !important;
}
[data-testid="stSelectbox"]>div>div{
    border-radius:12px !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] *{
    color:var(--ink) !important;
}
.instruction-box{
    background:#fff7fb;border:1px solid #f4c4d8;border-left:4px solid var(--pink);
    border-radius:13px;padding:14px 16px;margin:4px 0 20px;
    color:var(--ink);font-size:14px;line-height:1.55;
}
.instruction-box strong{color:var(--pink);}
.demo-qr{
    width:190px;height:190px;margin:10px auto 18px;padding:10px;background:#fff;
    border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 22px rgba(20,30,50,.07);
}
.demo-qr-grid{
    width:100%;height:100%;display:grid;grid-template-columns:repeat(15,1fr);
    background:#fff;
}
.demo-qr-grid i{background:#172033;display:block;}
.demo-qr-grid i.off{background:#fff;}
.qr-caption{text-align:center;color:var(--muted);font-size:13px;margin-bottom:18px;}
.stDataFrame{border-radius:15px;overflow:hidden;}

@media(max-width:800px){
    .block-container{padding:20px 14px 105px !important;}
    .hello{font-size:25px;}
    .balance-amount{font-size:36px;}
    .card-number{font-size:18px;}
}

/* ---- Header bar: hamburger / search / notification / profile ---- */
[data-testid="stElementContainer"]:has(.burger-marker) + [data-testid="stElementContainer"] .stButton>button,
[data-testid="stElementContainer"]:has(.sidebar-collapse-marker) + [data-testid="stElementContainer"] .stButton>button,
[data-testid="stElementContainer"]:has(.sidebar-collapsed-marker) + [data-testid="stElementContainer"] .stButton>button{
    border-radius:50% !important;background:#fff !important;border:1px solid var(--line) !important;
    font-size:17px !important;padding:0 !important;box-shadow:0 5px 16px rgba(20,30,50,.07) !important;
}
[data-testid="stElementContainer"]:has(.bell-btn-marker) + [data-testid="stElementContainer"] .stButton>button{
    border-radius:50% !important;background:#fff !important;border:1px solid var(--line) !important;
    font-weight:800 !important;font-size:14px !important;box-shadow:0 5px 16px rgba(20,30,50,.07) !important;
}
[data-testid="stElementContainer"]:has(.profile-btn-marker) + [data-testid="stElementContainer"] .stButton>button{
    border-radius:999px !important;background:linear-gradient(135deg,#E91E63,#7B1FA2) !important;
    color:#fff !important;border:none !important;font-weight:800 !important;font-size:13px !important;
    box-shadow:0 6px 16px rgba(123,31,162,.25) !important;
}
/* ===== Premium Bank Style Profile ===== */
[data-testid="stElementContainer"]:has(.profile-btn-marker) button{
    width:44px !important;
    height:44px !important;
    min-width:44px !important;
    padding:0 !important;

    border-radius:50% !important;

    background:linear-gradient(
        145deg,
        #0f172a 0%,
        #1e293b 55%,
        #312e81 100%
    ) !important;

    border:1px solid rgba(255,255,255,.18) !important;

    color:#ffffff !important;
    font-size:17px !important;
    font-weight:700 !important;

    box-shadow:
        0 6px 18px rgba(15,23,42,.28),
        inset 0 1px 1px rgba(255,255,255,.12) !important;
}
[data-testid="stElementContainer"]:has(.eye-btn-marker) + [data-testid="stElementContainer"] .stButton>button,
[data-testid="stElementContainer"]:has(.tx-toggle-marker) + [data-testid="stElementContainer"] .stButton>button,
[data-testid="stElementContainer"]:has(.tx-viewall-marker) + [data-testid="stElementContainer"] .stButton>button{
    font-size:12px !important;font-weight:700 !important;min-height:38px !important;
}
[data-testid="stForm"]{border:none !important;padding:0 !important;background:transparent !important;}
[data-testid="stForm"] [data-testid="stTextInput"] input{
    border-radius:999px !important;background:#fff !important;padding-left:16px !important;
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button{
    border-radius:50% !important;background:#fff !important;
}

/* ---- Notification / profile dropdown panels ---- */
.dropdown-panel{
    background:#fff;border:1px solid var(--line);border-radius:18px;
    padding:16px 18px;margin:0 0 20px;box-shadow:0 10px 26px rgba(20,30,50,.08);
}
.dropdown-title{font-size:15px;font-weight:800;margin-bottom:10px;}
.dropdown-empty{color:var(--muted);font-size:13px;padding:8px 0;}
.notif-row{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #f0f1f4;}
.notif-row:last-of-type{border-bottom:0;}
.notif-icon{width:34px;height:34px;border-radius:50%;background:#fff6df;display:flex;align-items:center;justify-content:center;font-size:15px;flex:none;}
.notif-title{font-weight:750;font-size:13.5px;}
.notif-sub{font-size:11.5px;color:var(--muted);margin-top:2px;}
.profile-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f0f1f4;font-size:13.5px;}
.profile-row:last-child{border-bottom:0;}
.profile-row span{color:var(--muted);}

/* ---- "Experience the New Way to Pay" promo card (side rail) ---- */
.new-way-card{
    border-radius:22px;padding:24px 22px;color:#fff;margin-top:18px;
    background:linear-gradient(135deg,#8E24AA 0%,#6A1B9A 60%,#4A148C 100%);
    box-shadow:0 16px 34px rgba(90,20,140,.25);
}
.new-way-title{font-size:19px;font-weight:800;line-height:1.3;}
.new-way-sub{font-size:12.5px;margin-top:10px;opacity:.92;line-height:1.6;font-weight:500;}

/* ==================================================
   Auth (Sign In / Sign Up) page — Codex Pay identity
   ================================================== */
.auth-page{position:relative;max-width:1180px;margin:0 auto;padding:10px 4px 40px;}
.auth-glow-a,.auth-glow-b{
    position:fixed;border-radius:50%;z-index:0;pointer-events:none;
}
.auth-glow-a{
    top:-160px;left:-160px;width:440px;height:440px;
    background:radial-gradient(circle,rgba(233,30,99,.20) 0%,rgba(233,30,99,0) 70%);
}
.auth-glow-b{
    bottom:-180px;right:-180px;width:480px;height:480px;
    background:radial-gradient(circle,rgba(123,31,162,.18) 0%,rgba(123,31,162,0) 70%);
}

/* ---- Hero: logo + wordmark ---- */
.auth-hero{position:relative;z-index:1;text-align:center;margin-bottom:6px;}
.auth-logo-badge{
    width:62px;height:62px;border-radius:18px;margin:0 auto 10px;
    background:linear-gradient(135deg,#E91E63,#7B1FA2);
    display:flex;align-items:center;justify-content:center;font-size:27px;
    box-shadow:0 12px 26px rgba(123,31,162,.28);color:#fff;
}
.auth-wordmark{font-size:36px;font-weight:900;letter-spacing:.3px;}
.auth-wordmark .navy{color:var(--ink);}
.auth-wordmark .pink{color:var(--pink);}
.auth-tagline{color:var(--muted);margin:4px 0 26px;font-size:14.5px;font-weight:600;}

/* ---- Left: promo panel ---- */
.promo-panel{
    position:relative;
    z-index:1;
    overflow:hidden;
    border-radius:26px;
    padding:32px 28px;
    min-height:230px;

    width:92%;
    margin:0 auto;
    box-sizing:border-box;

    color:#fff;
    background: linear-gradient(
    135deg,
    #0B0510 0%,
    #2B0C26 35%,
    #6B1B5D 65%,
    #C02AD1 100%
);
   box-shadow:
    0 24px 55px rgba(38, 8, 50, .38),
    0 8px 24px rgba(140, 43, 175, .18),
    inset 0 1px 0 rgba(255,255,255,.14);
}
.promo-panel:before{
    content:"";position:absolute;width:220px;height:220px;right:-70px;top:-70px;
    border-radius:50%;background:rgba(255,255,255,.10);
}
.promo-panel:after{
    content:"";position:absolute;width:150px;height:150px;left:-50px;bottom:-60px;
    border-radius:50%;background:rgba(255,255,255,.08);
}
.promo-heading{font-size:25px;font-weight:800;line-height:1.35;position:relative;z-index:2;}
.promo-sub{font-size:13.5px;margin-top:10px;max-width:300px;opacity:.94;
    line-height:1.6;position:relative;z-index:2;font-weight:500;}

.promo-visual{position:relative;z-index:2;height:150px;margin-top:22px;
    display:flex;align-items:flex-end;justify-content:center;}
.promo-phone{
    width:118px;background:#0d1526;border-radius:16px;padding:9px 9px 12px;
    box-shadow:0 18px 30px rgba(0,0,0,.35);position:relative;z-index:2;
}
.promo-phone-brand{color:#fff;font-size:9px;font-weight:800;letter-spacing:.4px;
    display:flex;align-items:center;gap:3px;margin-bottom:6px;}
.promo-phone-card{
    background:linear-gradient(135deg,#7B1FA2,#E91E63);border-radius:9px;
    padding:9px 8px;color:#fff;
}
.promo-phone-label{font-size:7.5px;opacity:.85;font-weight:600;}
.promo-phone-amount{font-size:12.5px;font-weight:800;margin-top:3px;}
.promo-badge{
    position:absolute;width:34px;height:34px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-size:15px;
    box-shadow:0 8px 18px rgba(0,0,0,.22);z-index:3;
}
.promo-badge.b1{background:#FF6D00;color:#fff;left:14%;bottom:22px;}
.promo-badge.b2{background:#fff;color:var(--pink);right:12%;top:6px;}
.promo-badge.b3{background:#17203A;color:#fff;right:20%;bottom:6px;}

.promo-feature-card{
    position:relative;z-index:1;background:#fff;border-radius:20px;
    padding:20px 18px;margin-top:16px;box-shadow:0 12px 30px rgba(20,20,40,.07);
}
.promo-feature-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 12px;}
.promo-feature-cell{display:flex;align-items:flex-start;gap:10px;}
.promo-feature-ico{
    width:38px;height:38px;min-width:38px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-size:16px;color:#fff;
}
.promo-feature-title{font-weight:800;font-size:12.5px;color:var(--ink);}
.promo-feature-sub{color:var(--muted);font-size:10.5px;margin-top:1px;}

.promo-strip{
    position:relative;z-index:1;display:flex;justify-content:space-between;
    flex-wrap:wrap;gap:10px 16px;margin-top:14px;padding:2px 4px;
}
.promo-strip-item{display:flex;align-items:center;gap:6px;font-size:11.5px;
    font-weight:700;color:var(--ink);}

/* ---- Right: login card ---- */
.login-card{
    position:relative;z-index:1;background:#fff;border-radius:26px;
    padding:6px 26px 26px;box-shadow:0 22px 50px rgba(30,10,60,.14);
}
.auth-tabs{display:flex;border-bottom:2px solid var(--line);margin:0 0 20px;}
.auth-tabs .stButton{flex:1;}
.auth-tabs .stButton>button{
    background:transparent !important;border:none !important;border-radius:0 !important;
    box-shadow:none !important;font-weight:800 !important;font-size:14.5px !important;
    padding:12px 0 !important;color:var(--muted) !important;
    border-bottom:3px solid transparent !important;margin-bottom:-2px !important;
}
.auth-tabs .stButton>button:hover{color:var(--pink) !important;}
.auth-tabs .stButton>button[kind="primary"]{
    color:var(--pink) !important;border-bottom:3px solid var(--pink) !important;
}
.auth-avatar{
    width:56px;height:56px;border-radius:50%;margin:4px auto 12px;
    background:linear-gradient(135deg,#E91E63,#7B1FA2);
    display:flex;align-items:center;justify-content:center;color:#fff;font-size:23px;
    box-shadow:0 10px 22px rgba(123,31,162,.28);
}
.auth-welcome{font-size:21px;font-weight:800;text-align:center;color:var(--ink);}
.auth-sub{color:var(--muted);text-align:center;font-size:13.5px;margin:4px 0 20px;font-weight:600;}
.field-label{font-size:13.5px;font-weight:800;color:var(--ink);margin:14px 0 3px;}
.field-hint{font-size:11.5px;color:var(--muted);margin-bottom:6px;line-height:1.5;}
.forgot-link{
    display:block;text-align:right;color:var(--pink);font-size:12.5px;
    font-weight:700;margin:6px 0 16px;
}
[data-testid="stElementContainer"]:has(.forgot-btn-marker) + [data-testid="stElementContainer"]{
    text-align:right;margin:2px 0 14px;
}
[data-testid="stElementContainer"]:has(.forgot-btn-marker) + [data-testid="stElementContainer"] .stButton{
    display:inline-block;
}
[data-testid="stElementContainer"]:has(.forgot-btn-marker) + [data-testid="stElementContainer"] .stButton>button{
    background:transparent !important;border:none !important;box-shadow:none !important;
    color:var(--pink) !important;font-size:12.5px !important;font-weight:700 !important;
    padding:0 !important;min-height:auto !important;
}
[data-testid="stElementContainer"]:has(.forgot-btn-marker) + [data-testid="stElementContainer"] .stButton>button:hover{
    color:var(--pink-dark) !important;text-decoration:underline !important;
}
[data-testid="stElementContainer"]:has(.back-link-marker) + [data-testid="stElementContainer"]{
    text-align:left;margin:0 0 10px;
}
[data-testid="stElementContainer"]:has(.back-link-marker) + [data-testid="stElementContainer"] .stButton{
    display:inline-block;
}
[data-testid="stElementContainer"]:has(.back-link-marker) + [data-testid="stElementContainer"] .stButton>button{
    background:transparent !important;border:none !important;box-shadow:none !important;
    color:var(--muted) !important;font-size:12.5px !important;font-weight:700 !important;
    padding:0 !important;min-height:auto !important;
}
[data-testid="stElementContainer"]:has(.back-link-marker) + [data-testid="stElementContainer"] .stButton>button:hover{
    color:var(--pink) !important;text-decoration:underline !important;
}
.auth-promo-banner{
    background:linear-gradient(135deg,#FDF0F6 0%,#F4EAFA 100%);
    border:1px solid #f3d9ec;border-radius:16px;
    padding:12px 16px;margin:0 0 18px;text-align:center;
    font-weight:800;font-size:13.5px;color:var(--purple);line-height:1.5;
}
.trust-box{
    background:#F4EAFA;border:1px solid #eadcf7;border-radius:14px;
    padding:13px 15px;margin:16px 0 4px;
    display:flex;gap:10px;align-items:flex-start;font-size:12.5px;color:var(--ink);
}
.trust-box b{color:var(--purple);display:block;font-size:13.5px;}
.demo-hint{color:var(--muted);font-size:11.5px;text-align:center;margin-top:14px;line-height:1.6;}
.auth-footer{text-align:center;color:var(--muted);font-size:12px;margin:26px 0 4px;}

@media(max-width:900px){
    .auth-page{padding:6px 2px 30px;}
    .auth-wordmark{font-size:29px;}
    .promo-panel{padding:24px 20px;}
    .promo-heading{font-size:21px;}
    .login-card{padding:4px 18px 20px;margin-top:18px;}
}
</style>
""", unsafe_allow_html=True)

# ---------- Session ----------
if "session_user" not in st.session_state:
    st.session_state.session_user = None
if "tab" not in st.session_state:
    st.session_state.tab = "Home"
if "service" not in st.session_state:
    st.session_state.service = None
if "req_amount" not in st.session_state:
    st.session_state.req_amount = 100.0
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = True
if "show_notif" not in st.session_state:
    st.session_state.show_notif = False
if "show_profile" not in st.session_state:
    st.session_state.show_profile = False
if "balance_hidden" not in st.session_state:
    st.session_state.balance_hidden = False
if "show_tx_panel" not in st.session_state:
    st.session_state.show_tx_panel = True

def api(method, path, payload=None):
    try:
        if method == "GET":
            r = requests.get(API + path, timeout=8)
        else:
            r = requests.post(API + path, json=payload, timeout=8)
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code >= 400:
            return None, data.get("detail", f"HTTP {r.status_code}")
        return data, None
    except requests.exceptions.ConnectionError:
        return None, "Backend is not running. Start FastAPI on port 8000."
    except requests.exceptions.Timeout:
        return None, "Backend timeout. Please retry."

def esc(value):
    return html.escape(str(value))

def error_box(message):
    st.markdown(f"<div class='error-box'>✕ {esc(message)}</div>", unsafe_allow_html=True)

def password_field(label, placeholder, key):
    """
    A plain password text_input. Streamlit's own show/hide button sits
    inside the field already (see the stTextInputRevealButton CSS fix
    above, which swaps its broken icon font for an actual eye emoji) —
    so this is just a thin wrapper for consistent placeholders/keys.
    """
    return st.text_input(
        label, type="password", placeholder=placeholder,
        key=key, label_visibility="collapsed",
    )

@st.dialog("Transaction Successful")
def success_dialog(message, reference=None, offer_home=False):
    st.markdown("<div class='success-box'>✓ Successful</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:15px 0 5px;font-weight:700;color:#172033'>{esc(message)}</p>", unsafe_allow_html=True)
    if reference:
        st.caption(f"Reference: {reference}")
    if offer_home:
        c1, c2 = st.columns(2, gap="small")
        with c1:
            if st.button("Done", use_container_width=True):
                st.rerun()
        with c2:
            st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
            if st.button("Back to Home", use_container_width=True):
                st.session_state.tab = "Home"
                st.session_state.service = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        if st.button("Done", type="primary", use_container_width=True):
            st.rerun()

def run_transaction(path, payload, message):
    result, err = api("POST", path, payload)
    if err:
        error_box(err)
        return
    success_dialog(message, result.get("transaction_reference_id"), offer_home=True)

def open_service(name):
    st.session_state.service = name
    st.session_state.tab = "Service"
    st.rerun()

def go_tab(name):
    st.session_state.tab = name
    if name != "Service":
        st.session_state.service = None
    st.rerun()

def balance_for(uid):
    data, err = api("GET", f"/account-balance/{uid}")
    if err:
        return {"current_available_balance": 0, "status": "UNKNOWN"}
    return data

# ---------- Login ----------
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "signin"   # "signin" | "signup" | "forgot"
if "forgot_verified" not in st.session_state:
    # None until Step 1 (identity check) succeeds, then holds the
    # {"user_id","username","full_name"} dict returned by /verify-identity.
    st.session_state.forgot_verified = None


def login():
    # Light fintech background for the auth page only — this <style> tag is
    # only emitted while session_user is None (see router at the bottom of
    # this file), so the dashboard keeps its own background once signed in.
    st.markdown("""
    <style>.stApp{background:var(--bg-light) !important;}</style>
    <div class='auth-glow-a'></div><div class='auth-glow-b'></div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='auth-page'>", unsafe_allow_html=True)

    # ---- Hero: logo, wordmark, tagline (plain content, no widgets) ----
    st.markdown(f"""
    <div class='auth-hero'>
        <div class='auth-logo-badge'>{CODEX_LOGO_SVG}</div>
        <div class='auth-wordmark'><span class='navy'>CODEX</span> <span class='pink'>PAY</span></div>
        <div class='auth-tagline'>Your Simple Digital Wallet</div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([11, 9], gap="large")

    # =========================================================
    # LEFT — promotional panel + feature card + trust strip
    # =========================================================
    with left:
        st.markdown("""
        <div class='promo-panel'>
            <div class='promo-heading'>সব পেমেন্ট<br>এক ওয়ালেটে</div>
            <div class='promo-sub'>Send money, pay bills, and recharge — all in one
                simple, secure Codex Pay wallet.</div>
            <div class='promo-visual'>
                <div class='promo-phone'>
                    <div class='promo-phone-brand'>💳 CODEX PAY</div>
                    <div class='promo-phone-card'>
                        <div class='promo-phone-label'>Available Balance</div>
                        <div class='promo-phone-amount'>৳ 25,680.50</div>
                    </div>
                </div>
                <div class='promo-badge b1'>➤</div>
                <div class='promo-badge b2'>💳</div>
                <div class='promo-badge b3'>🛡️</div>
            </div>
        </div>
        <div class='promo-feature-card'>
            <div class='promo-feature-grid'>
                <div class='promo-feature-cell'>
                    <div class='promo-feature-ico' style='background:#E91E63'>➤</div>
                    <div><div class='promo-feature-title'>Instant Transfer</div>
                    <div class='promo-feature-sub'>Send money in seconds</div></div>
                </div>
                <div class='promo-feature-cell'>
                    <div class='promo-feature-ico' style='background:#FF6D00'>🏧</div>
                    <div><div class='promo-feature-title'>Cash Out</div>
                    <div class='promo-feature-sub'>Easy & secure</div></div>
                </div>
                <div class='promo-feature-cell'>
                    <div class='promo-feature-ico' style='background:#7B1FA2'>🧾</div>
                    <div><div class='promo-feature-title'>Bill Payment</div>
                    <div class='promo-feature-sub'>Pay any bill instantly</div></div>
                </div>
                <div class='promo-feature-cell'>
                    <div class='promo-feature-ico' style='background:#17203A'>🛡️</div>
                    <div><div class='promo-feature-title'>Secure & Reliable</div>
                    <div class='promo-feature-sub'>Your money, protected</div></div>
                </div>
            </div>
        </div>
        <div class='promo-strip'>
            <div class='promo-strip-item'>🛡️ Secure Transactions</div>
            <div class='promo-strip-item'>🎧 Customer Support</div>
            <div class='promo-strip-item'>⚡ Fast & Reliable</div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================
    # RIGHT — Sign In / Sign Up card
    # =========================================================
    with right:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)

        # ---- Bangla promo banner (the box above the Sign In / Sign Up tabs) ----
        st.markdown(
            "<div class='auth-promo-banner'>✨ কোনো ঝামেলা ছাড়াই, একদম সহজে পেমেন্ট করুন</div>",
            unsafe_allow_html=True,
        )

        # ---- Sign In / Sign Up tabs (underline style) ----
        st.markdown("<div class='auth-tabs'>", unsafe_allow_html=True)
        tab_col_1, tab_col_2 = st.columns(2, gap="small")
        with tab_col_1:
            if st.button("Sign In", key="auth_tab_signin", use_container_width=True,
                          type="primary" if st.session_state.auth_mode in ("signin", "forgot") else "secondary"):
                st.session_state.auth_mode = "signin"
                st.session_state.forgot_verified = None
                st.rerun()
        with tab_col_2:
            if st.button("Sign Up", key="auth_tab_signup", use_container_width=True,
                          type="primary" if st.session_state.auth_mode == "signup" else "secondary"):
                st.session_state.auth_mode = "signup"
                st.session_state.forgot_verified = None
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.auth_mode == "signin":
            st.markdown("""
            <div class='auth-avatar'>👤</div>
            <div class='auth-welcome'>Welcome Back!</div>
            <div class='auth-sub'>Sign in to continue to your account</div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='field-label'>User ID or Username</div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='field-hint'>Enter your User ID (e.g. 1024) or username (e.g. rafiq)</div>",
                unsafe_allow_html=True,
            )
            identifier = st.text_input(
                "User ID or Username", placeholder="Enter User ID or Username",
                key="signin_identifier", label_visibility="collapsed",
            )

            st.markdown("<div class='field-label'>Password</div>", unsafe_allow_html=True)
            password = password_field(
                "Password", "Enter your password", "signin_password",
            )

            st.markdown("<div class='forgot-btn-marker'></div>", unsafe_allow_html=True)
            if st.button("Forgot Password?", key="open_forgot"):
                st.session_state.auth_mode = "forgot"
                st.session_state.forgot_verified = None
                st.rerun()

            st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
            if st.button("🔒 Sign In", use_container_width=True, key="do_signin"):
                if not identifier.strip() or not password:
                    # Client-side check first: don't hit the backend for an
                    # obviously-empty form, and don't show a generic "invalid
                    # credentials" error for a field the person just forgot.
                    error_box("Please enter your User ID/Username and password.")
                else:
                    result, err = api("POST", "/authenticate-user", {
                        "identifier": identifier.strip(),
                        "password": password,
                    })
                    if err:
                        error_box(err)
                    else:
                        st.session_state.session_user = result
                        st.session_state.tab = "Home"
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("""
            <div class='trust-box'>🛡️<div><b>Secure. Fast. Reliable.</b>Your money is protected with us.</div></div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class='demo-hint'>Demo accounts — rafiq/rafiq123 (1024) · prince/prince123 (2048)<br>
            tahmid/tahmid123 (3072) · emon/emon123 (4096)</div>
            """, unsafe_allow_html=True)

        elif st.session_state.auth_mode == "forgot":
            st.markdown("<div class='back-link-marker'></div>", unsafe_allow_html=True)
            if st.button("← Back to Sign In", key="forgot_back"):
                st.session_state.auth_mode = "signin"
                st.session_state.forgot_verified = None
                st.rerun()

            if st.session_state.forgot_verified is None:
                # ---- Step 1: confirm the account exists ----
                st.markdown("""
                <div class='auth-avatar'>🔑</div>
                <div class='auth-welcome'>Forgot Password?</div>
                <div class='auth-sub'>Enter your User ID or username to continue</div>
                """, unsafe_allow_html=True)

                st.markdown("<div class='field-label'>User ID or Username</div>", unsafe_allow_html=True)
                st.markdown(
                    "<div class='field-hint'>Enter your User ID (e.g. 1024) or username (e.g. rafiq)</div>",
                    unsafe_allow_html=True,
                )
                forgot_identifier = st.text_input(
                    "User ID or Username", placeholder="Enter User ID or Username",
                    key="forgot_identifier", label_visibility="collapsed",
                )

                st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
                if st.button("Continue", use_container_width=True, key="do_forgot_verify"):
                    if not forgot_identifier.strip():
                        error_box("Please enter your User ID or username.")
                    else:
                        result, err = api("POST", "/verify-identity", {
                            "identifier": forgot_identifier.strip(),
                        })
                        if err:
                            error_box(err)
                        else:
                            st.session_state.forgot_verified = result
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            else:
                # ---- Step 2: identity confirmed, set a new password ----
                verified = st.session_state.forgot_verified
                st.markdown("""
                <div class='auth-avatar'>🔑</div>
                <div class='auth-welcome'>Set a New Password</div>
                """, unsafe_allow_html=True)
                st.markdown(
                    f"<div class='auth-sub'>Account found — {esc(verified['full_name'])} "
                    f"(User ID: {esc(verified['user_id'])})</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("<div class='field-label'>New Password</div>", unsafe_allow_html=True)
                reset_password_val = password_field(
                    "New Password", "At least 6 characters", "reset_new_password",
                )

                st.markdown("<div class='field-label'>Confirm New Password</div>", unsafe_allow_html=True)
                reset_confirm_val = password_field(
                    "Confirm New Password", "Re-enter your new password",
                    "reset_confirm_password",
                )

                st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
                if st.button("🔒 Reset Password", use_container_width=True, key="do_reset_password"):
                    if reset_password_val != reset_confirm_val:
                        error_box("Passwords do not match.")
                    elif len(reset_password_val) < 6:
                        error_box("Password must be at least 6 characters.")
                    else:
                        result, err = api("POST", "/reset-password", {
                            "identifier": verified["user_id"],
                            "new_password": reset_password_val,
                        })
                        if err:
                            error_box(err)
                        else:
                            st.session_state.forgot_verified = None
                            st.session_state.auth_mode = "signin"
                            st.success("Password reset! Please sign in with your new password.")
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.markdown("""
            <div class='auth-avatar'>📝</div>
            <div class='auth-welcome'>Create Account</div>
            <div class='auth-sub'>Sign up for your free Codex Pay wallet</div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='field-label'>Full Name</div>", unsafe_allow_html=True)
            full_name = st.text_input("Full Name", placeholder="e.g. Rafiq Rahman",
                                       key="signup_full_name", label_visibility="collapsed")

            st.markdown("<div class='field-label'>Choose a Username</div>", unsafe_allow_html=True)
            new_username = st.text_input(
                "Choose a Username", placeholder="letters, numbers, underscore — e.g. rafiq",
                key="signup_username", label_visibility="collapsed",
            )

            st.markdown("<div class='field-label'>User ID (optional)</div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='field-hint'>Choose a 4-digit User ID, or leave blank to auto-generate</div>",
                unsafe_allow_html=True,
            )
            new_user_id = st.text_input(
                "User ID (optional)", max_chars=4, placeholder="e.g. 1024",
                key="signup_user_id", label_visibility="collapsed",
            )

            st.markdown("<div class='field-label'>Create Password</div>", unsafe_allow_html=True)
            new_password = password_field(
                "Create Password", "At least 6 characters", "signup_password",
            )

            st.markdown("<div class='field-label'>Confirm Password</div>", unsafe_allow_html=True)
            confirm_password = password_field(
                "Confirm Password", "Re-enter your password",
                "signup_confirm_password",
            )

            st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
            if st.button("🔒 Sign Up", use_container_width=True, key="do_signup"):
                if not full_name.strip() or not new_username.strip():
                    error_box("Full name and username are required.")
                elif new_password != confirm_password:
                    error_box("Passwords do not match.")
                elif len(new_password) < 6:
                    error_box("Password must be at least 6 characters.")
                else:
                    result, err = api("POST", "/signup", {
                        "full_name": full_name.strip(),
                        "username": new_username.strip(),
                        "user_id": new_user_id.strip() or None,
                        "password": new_password,
                    })
                    if err:
                        error_box(err)
                    else:
                        st.session_state.session_user = result
                        st.session_state.tab = "Home"
                        st.session_state.auth_mode = "signin"
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("""
            <div class='trust-box'>🎁<div><b>Welcome Bonus</b>New accounts start with ৳1,000.00 demo balance.</div></div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)  # close .login-card

    st.markdown("<div class='auth-footer'>© 2024 Codex Pay. All rights reserved.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)  # close .auth-page

# ---------- Sidebar ----------
# (icon, label, tab this item routes to)
SIDEBAR_NAV = [
    ("⌂", "Home", "Home"),
    ("⊞", "Services", "Service"),
    ("▤", "Cards", "Account"),
    ("▥", "Transactions", "Transactions"),
    ("♟", "Requests", "Requests"),
    ("？", "Support", "Support"),
]

def sidebar(active_tab):
    st.markdown("<div class='sidebar-collapse-marker'></div>", unsafe_allow_html=True)
    if st.button("☰", key="collapse_sidebar", use_container_width=True):
        st.session_state.sidebar_open = False
        st.rerun()

    st.markdown(f"""
        <div class='sidebar-brand'>
        <div class='sidebar-logo-badge'>{CODEX_LOGO_SVG}</div>
        <div class='sidebar-wordmark'><span class='navy'>CODEX</span> <span class='pink'>PAY</span></div>
        <div class='sidebar-tagline'>Your Simple Digital Wallet</div>
        </div>
    """, unsafe_allow_html=True)

    for icon, label, tab in SIDEBAR_NAV:
        is_active = (active_tab == tab)
        st.markdown(f"<div class='side-nav-marker{' active' if is_active else ''}'></div>", unsafe_allow_html=True)
        if st.button(f"{icon}   {label}", key=f"side_{tab}", use_container_width=True):
            go_tab(tab)

    st.markdown("<div class='side-nav-marker'></div>", unsafe_allow_html=True)
    if st.button("⇥   Log Out", key="side_logout", use_container_width=True):
        st.session_state.session_user = None
        st.session_state.tab = "Home"
        st.rerun()

    st.markdown("""
    <div class='sidebar-promo'>
        <div style='font-size:18px'>🛡️</div>
        <div class='sidebar-promo-title'>Security Center</div>
        <div class='sidebar-promo-sub'>Keep your account safe and secure</div>
    </div>
    <div class='sidebar-promo support' style='margin-top:12px'>
        <div style='font-size:18px'>🎧</div>
        <div class='sidebar-promo-title'>24/7 Support</div>
        <div class='sidebar-promo-sub'>We're here to help you anytime</div>
    </div>
    """, unsafe_allow_html=True)

def trust_strip():
    st.markdown("""
    <div class='trust-strip'>
        <div class='trust-strip-item'>
            <div class='trust-strip-ico' style='background:var(--pink)'>🛡️</div>
            <div><div class='trust-strip-title'>Secure. Fast. Reliable.</div>
            <div class='trust-strip-sub'>Your money is always protected with us.</div></div>
        </div>
        <div class='trust-strip-item'>
            <div class='trust-strip-ico' style='background:#2e7d32'>✓</div>
            <div><div class='trust-strip-title'>Bank Level Security</div>
            <div class='trust-strip-sub'>Your data is 100% protected</div></div>
        </div>
        <div class='trust-strip-item'>
            <div class='trust-strip-ico' style='background:#f9a825'>⚡</div>
            <div><div class='trust-strip-title'>Fast & Reliable</div>
            <div class='trust-strip-sub'>Instant & reliable services</div></div>
        </div>
        <div class='trust-strip-item'>
            <div class='trust-strip-ico' style='background:#7B1FA2'>🔒</div>
            <div><div class='trust-strip-title'>Trusted Platform</div>
            <div class='trust-strip-sub'>Safe, secure & reliable</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------- Card ----------
def demo_card(user):
    data, err = api("GET", f"/cards/{user['user_id']}")
    if data and not err:
        return data[0]
    uid = user["user_id"]
    return {
        "card_id": None,
        "card_name": "Codex Visa",
        "last4": uid,
        "expiry": "12/30",
        "account_number": f"CODX-{uid}-0001",
        "cardholder_name": user["full_name"],
        "blocked": 0,
        "card_balance": 50000.00,
    }

def card_html(card):
    # Demo/placeholder card number derived from the user's last4 — no real
    # bank name or logo is used, matching the "no copyrighted bank artwork"
    # requirement while still giving the premium dark debit-card look.
    number = f"4213 6800 1234 {card['last4']}"
    holder = (card.get('cardholder_name') or card.get('card_name') or '').upper()
    return f"""
    <div class='debit-card'>
        <div class='debit-head'>
            <div>
                <div class='debit-bank-icon'>🏦</div>
                <div class='debit-bank-name'>Codex Bank</div>
                <div class='debit-bank-sub'>Digital Banking PLC.</div>
            </div>
            <div class='debit-type'>DEBIT CARD</div>
        </div>
        <div class='debit-chip-row'>
            <div class='debit-chip'></div>
            <div class='debit-wave'>))</div>
        </div>
        <div class='debit-number'>{esc(number)}</div>
        <div class='debit-foot'>
            <div>
                <div class='debit-name'>{esc(holder)}</div>
                <div class='debit-acct'>{esc(card.get('account_number') or 'CODX-DEMO-0001')}</div>
            </div>
            <div class='debit-valid'>VALID THRU<b>{esc(card['expiry'])}</b></div>
        </div>
        <div style='display:flex;justify-content:flex-end;margin-top:8px'>
            <div class='debit-visa'>VISA</div>
        </div>
    </div>
    """

# ---------- Home ----------
# (icon, name, sub, icon-bg, button-css-class, button-label)
QUICK = [
    ("➤", "Send Money", "Send to any user", "#fff0f7", "quick-send", "Send Now"),
    ("📱", "Mobile Recharge", "Top up your mobile", "#f3e9ff", "quick-recharge", "Recharge"),
    ("💵", "Cash Out", "Withdraw your cash", "#ffece3", "quick-cashout", "Cash Out"),
    ("🧾", "Pay Bill", "Pay your bills easily", "#e4f9f0", "quick-paybill", "Pay Now"),
]

SERVICES = [
    ("🏪", "Make Payment", "Pay to any merchant", "#fff0f2"),
    ("▦", "QR Payment", "Scan & Pay instantly", "#f3efff"),
    ("🛣️", "E-Toll", "Easy toll payments", "#eaf8f1"),
    ("💳", "Cards", "Manage your cards", "#edf4ff"),
    ("◔", "Balance Inquiry", "Check your balance", "#f7ecff"),
    ("📄", "Mini Statement", "View recent transactions", "#fff0f2"),
    ("🕐", "Transaction History", "See all transactions", "#edf8ff"),
    ("♙", "Request Money", "Request from others", "#fff6df"),
    ("🔔", "Notification", "View all notifications", "#edf4ff"),
    ("🎧", "Help & Support", "Get help & support", "#e4f9f0"),
]

def recent_transactions(user_id):
    data, err = api("GET", f"/transaction-history/{user_id}?limit=4&offset=0")
    if err or not data:
        st.markdown("""
        <div class='tx-card'><div style='padding:25px;text-align:center;color:#747d90'>
        No transactions yet.
        </div></div>
        """, unsafe_allow_html=True)
        return
    rows = []
    for x in data:
        t = x.get("transaction_type","").replace("_"," ").title()
        amount = float(x.get("transaction_amount",0))
        sender = x.get("sender_user_id")
        receiver = x.get("receiver_user_id")
        if sender == user_id:
            sign = "-"
            desc = f"To: {receiver or x.get('description','')}"
        else:
            sign = "+"
            desc = f"From: {sender or x.get('description','')}"
        rows.append(
            "<div class='tx-row'>"
            "<div class='tx-left'>"
            f"<div class='tx-icon'>{'↑' if sign=='-' else '↓'}</div>"
            f"<div><div class='tx-name'>{esc(t)}</div><div class='tx-desc'>{esc(desc)}</div></div>"
            "</div>"
            "<div class='tx-right'>"
            f"<div class='tx-amount'>{sign}৳{amount:,.2f}</div>"
            f"<div class='tx-time'>{esc(x.get('recorded_at',''))}</div>"
            "</div>"
            "</div>"
        )
    st.markdown("<div class='tx-card'>" + "".join(rows) + "</div>", unsafe_allow_html=True)

# ---------- Header bar: hamburger / search / notification / profile ----------
# (keyword, kind, target) — kind is "service" (open_service), "tab" (go_tab),
# or "notif" (open the notification panel). Matched as a substring against
# whatever the person typed, longest keyword first so "pay bill" wins over
# a looser "bill" for the same query.
SEARCH_MAP = [
    ("send money", "service", "Send Money"),
    ("mobile recharge", "service", "Mobile Recharge"),
    ("recharge", "service", "Mobile Recharge"),
    ("cash out", "service", "Cash Out"),
    ("pay bill", "service", "Pay Bill"),
    ("bill", "service", "Pay Bill"),
    ("make payment", "service", "Make Payment"),
    ("payment", "service", "Make Payment"),
    ("qr payment", "tab", "QR Payment"),
    ("qr", "tab", "QR Payment"),
    ("e-toll", "service", "E-Toll"),
    ("etoll", "service", "E-Toll"),
    ("toll", "service", "E-Toll"),
    ("cards", "tab", "Account"),
    ("card", "tab", "Account"),
    ("balance inquiry", "service", "Balance Inquiry"),
    ("balance", "service", "Balance Inquiry"),
    ("mini statement", "service", "Mini Statement"),
    ("statement", "service", "Mini Statement"),
    ("transaction history", "tab", "Transactions"),
    ("transactions", "tab", "Transactions"),
    ("request money", "tab", "Requests"),
    ("requests", "tab", "Requests"),
    ("notification", "notif", None),
    ("help & support", "tab", "Support"),
    ("help", "tab", "Support"),
    ("support", "tab", "Support"),
]

def run_search(query):
    q = query.lower().strip()
    for key, kind, target in sorted(SEARCH_MAP, key=lambda item: -len(item[0])):
        if key in q:
            if kind == "service":
                open_service(target)
            elif kind == "tab":
                go_tab(target)
            else:
                st.session_state.show_notif = True
                st.session_state.show_profile = False
                st.rerun()
            return True
    return False

def render_notif_panel(user):
    reqs = fetch_money_requests(user["user_id"])
    pending = [r for r in reqs["incoming"] if r["status"] == "pending"]
    st.markdown("<div class='dropdown-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='dropdown-title'>Notifications</div>", unsafe_allow_html=True)
    if not pending:
        st.markdown(
            "<div class='dropdown-empty'>You're all caught up — no pending requests.</div>",
            unsafe_allow_html=True,
        )
    else:
        rows = []
        for r in pending:
            rows.append(f"""
            <div class='notif-row'>
                <div class='notif-icon'>💸</div>
                <div>
                    <div class='notif-title'>Money Request</div>
                    <div class='notif-sub'>From User: {esc(r['requester_user_id'])} &bull; Amount: ৳{float(r['amount']):,.2f} &bull; Pending</div>
                </div>
            </div>
            """)
        st.markdown("".join(rows), unsafe_allow_html=True)
        st.markdown("<div class='primary-btn' style='margin-top:8px'>", unsafe_allow_html=True)
        if st.button("View All Requests", key="notif_view_all", use_container_width=True):
            st.session_state.show_notif = False
            go_tab("Requests")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_profile_panel(user):
    bal = balance_for(user["user_id"])
    st.markdown(f"""
    <div class='dropdown-panel'>
        <div class='dropdown-title'>My Profile</div>
        <div class='profile-row'><span>Name</span><b>{esc(user['full_name'])}</b></div>
        <div class='profile-row'><span>User ID</span><b>{esc(user['user_id'])}</b></div>
        <div class='profile-row'><span>Username</span><b>{esc(user['username'])}</b></div>
        <div class='profile-row'><span>Account Status</span><b>{esc(bal.get('status','ACTIVE'))}</b></div>
    </div>
    """, unsafe_allow_html=True)

def header_bar(user):
    incoming_count = pending_incoming_count(user["user_id"])

    c_search, c_notif, c_profile = st.columns([0.72, 0.11, 0.17], gap="small")

    with c_search:
        with st.form("search_form", clear_on_submit=True):
            sc1, sc2 = st.columns([0.9, 0.1], gap="small")
            with sc1:
                query = st.text_input(
                    "Search", placeholder="🔍  Search anything...",
                    label_visibility="collapsed", key="search_query",
                )
            with sc2:
                submitted = st.form_submit_button("→", use_container_width=True)
        if submitted:
            if query.strip() and not run_search(query):
                st.toast(f"No matching service found for “{query.strip()}”.")

    with c_notif:
        st.markdown("<div class='bell-btn-marker'></div>", unsafe_allow_html=True)
        label = f"🔔 {incoming_count}" if incoming_count else "🔔"
        if st.button(label, key="toggle_notif", use_container_width=True):
            st.session_state.show_notif = not st.session_state.show_notif
            st.session_state.show_profile = False
            st.rerun()

    with c_profile:
        st.markdown("<div class='profile-btn-marker'></div>", unsafe_allow_html=True)
        first_name = user["full_name"].split()[0] if user["full_name"].strip() else "Account"
        if st.button(f"◉ {first_name}", key="toggle_profile", use_container_width=True):
            st.session_state.show_profile = not st.session_state.show_profile
            st.session_state.show_notif = False
            st.rerun()

    if st.session_state.show_notif:
        render_notif_panel(user)
    if st.session_state.show_profile:
        render_profile_panel(user)

def home(user):
    bal = balance_for(user["user_id"])
    card = demo_card(user)

    st.markdown(f"""
    <div class='top-row'>
        <div>
            <div class='hello'>Hi, {esc(user['full_name'])} 👋</div>
            <div class='uid'>User ID: {esc(user['user_id'])} &bull; Welcome back!</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.04, 1.0], gap="large")
    with left:
        hidden = st.session_state.balance_hidden
        amount_display = "•••••••••" if hidden else f"৳{bal['current_available_balance']:,.2f}"
        st.markdown(f"""
        <div class='balance'>
            <div class='balance-top'>
                <div class='balance-label'>Available Balance</div>
            </div>
            <div class='balance-amount'>{amount_display}</div>
            <div class='status-line'>Account Status:
                <span class='status-pill'>{esc(bal.get('status','ACTIVE'))}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        add_col, eye_col = st.columns([0.7, 0.3], gap="small")
        with add_col:
            st.markdown("<div class='primary-btn' style='margin-top:12px'>", unsafe_allow_html=True)
            if st.button("+ Add Money", key="add_money_btn", use_container_width=True):
                open_service("Add Money")
            st.markdown("</div>", unsafe_allow_html=True)
        with eye_col:
            st.markdown("<div class='eye-btn-marker' style='margin-top:12px'></div>", unsafe_allow_html=True)
            if st.button("⊙ Hide" if not hidden else "👁 Show", key="toggle_balance_visibility", use_container_width=True):
                st.session_state.balance_hidden = not hidden
                st.rerun()
    with right:
        st.markdown(card_html(card), unsafe_allow_html=True)
        if card.get("card_id") and not card.get("blocked"):
            st.markdown("<div class='primary-btn' style='margin-top:12px'>", unsafe_allow_html=True)
            if st.button("⬇ Add to Wallet from Card", key="card_topup_home", use_container_width=True):
                open_service("Card Top-up")
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:3px'></div>", unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, (icon, name, sub, bg, btn_cls, btn_label) in zip(cols, QUICK):
        with col:
            st.markdown(f"""
            <div class='quick-card'>
                <div class='quick-icon' style='background:{bg}'>{icon}</div>
                <div class='quick-title'>{esc(name)}</div>
                <div class='quick-sub'>{esc(sub)}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"<div class='{btn_cls}-marker'></div>", unsafe_allow_html=True)
            if st.button(btn_label, key=f"quick_{name}", use_container_width=True):
                open_service(name)

    st.markdown("<div class='section-title'>Explore More Services</div>", unsafe_allow_html=True)
    for row_start in range(0, len(SERVICES), 5):
        cols = st.columns(5, gap="medium")
        for col, (icon, name, sub, bg) in zip(cols, SERVICES[row_start:row_start+5]):
            with col:
                st.markdown(f"""
                <div class='service-tile'>
                    <div class='service-icon' style='background:{bg}'>{icon}</div>
                    <div class='service-name'>{esc(name)}</div>
                    <div class='service-sub'>{esc(sub)}</div>
                """, unsafe_allow_html=True)
                st.markdown("<div class='service-button'>", unsafe_allow_html=True)
                if st.button("Open", key=f"home_service_{name}", use_container_width=True):
                    if name == "Cards":
                        go_tab("Account")
                    elif name == "Request Money":
                        go_tab("Requests")
                    elif name == "Notification":
                        st.session_state.show_notif = True
                        st.session_state.show_profile = False
                        st.rerun()
                    elif name == "Help & Support":
                        st.session_state.service = "Help & Support"
                        st.session_state.tab = "Service"
                        st.rerun()
                    else:
                        open_service(name)
                st.markdown("</div></div>", unsafe_allow_html=True)

    tcol1, tcol2, tcol3 = st.columns([0.7, 0.15, 0.15], gap="small")
    with tcol1:
        st.markdown("<div class='section-title'>Recent Transactions</div>", unsafe_allow_html=True)
    with tcol2:
        st.markdown("<div class='tx-toggle-marker'></div>", unsafe_allow_html=True)
        if st.button("Hide" if st.session_state.show_tx_panel else "👁", key="toggle_tx_panel", use_container_width=True):
            st.session_state.show_tx_panel = not st.session_state.show_tx_panel
            st.rerun()
    with tcol3:
        st.markdown("<div class='tx-viewall-marker'></div>", unsafe_allow_html=True)
        if st.button("View All", key="tx_view_all", use_container_width=True):
            go_tab("Transactions")

    if st.session_state.show_tx_panel:
        recent_transactions(user["user_id"])
    else:
        st.markdown(
            "<div class='tx-card'><div style='padding:20px;text-align:center;color:#747d90'>"
            "Transactions hidden.</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("""
    <div class='new-way-card'>
        <div class='new-way-title'>Experience the New Way to Pay</div>
        <div class='new-way-sub'>Fast. Secure. Reliable. All your payments in one simple app.</div>
    </div>
    """, unsafe_allow_html=True)

    trust_strip()


    
# ---------- Service Forms ----------
def service_instruction(name):
    instructions = {
        "Send Money": "<strong>Step 1:</strong> Enter the receiver's 4-digit User ID and the amount. Then press <b>Continue</b> to complete the transfer.",
        "Mobile Recharge": "<strong>Step 1:</strong> Enter the mobile number, choose the operator and enter the recharge amount.",
        "Cash Out": "<strong>Step 1:</strong> Select a demo ATM and enter the amount you want to withdraw.",
        "Pay Bill": "<strong>Step 1:</strong> Select the bill type and provider, enter your Customer/Meter ID, then enter the amount.",
        "Make Payment": "<strong>Step 1:</strong> Enter the merchant ID, merchant name and payment amount.",
        "QR Payment": "<strong>Step 1:</strong> Scan/use the demo QR or enter a receiver User ID, then enter the amount and press <b>Scan & Pay</b>.",
        "E-Toll": "<strong>Step 1:</strong> Enter your vehicle number, select the toll plaza and enter the toll amount.",
        "Balance Inquiry": "<strong>Instant:</strong> Your current available balance is shown below.",
        "Mini Statement": "<strong>Recent activity:</strong> Your latest transactions are shown below.",
        "Transaction History": "<strong>Full history:</strong> Your transaction records are shown below.",
        "Cards": "<strong>Demo card:</strong> View your card details here. No real bank card is connected.",
        "Add Money": "<strong>Demo:</strong> This service is shown for wallet navigation; no real bank rail is connected.",
        "Card Top-up": "<strong>Step 1:</strong> Enter how much to pull from your demo card's own balance into your wallet.",
        "Request Money": "<strong>Demo:</strong> This service is reserved for the next version.",
        "Help & Support": "<strong>Support:</strong> This is a demo wallet. Use the information below for project support details.",
    }
    return instructions.get(name, "<strong>Step 1:</strong> Enter the required information and continue.")


def service_form(name, user_id):
    st.markdown(f"""
    <div class='form-shell'>
        <div class='form-title'>{esc(name)}</div>
        <div class='form-sub'>Follow the instruction below to complete this service.</div>
        <div class='instruction-box'>{service_instruction(name)}</div>
    """, unsafe_allow_html=True)

    if name == "Send Money":
        receiver = st.text_input("Receiver User ID", max_chars=4, placeholder="2048")
        amount = st.number_input("Amount (৳)", min_value=0.01, max_value=1000000.0, value=100.0, step=50.0)
        note = st.text_input("Note (optional)")
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Continue", use_container_width=True):
            if len(receiver.strip()) != 4:
                error_box("Enter a valid 4-digit User ID.")
            else:
                run_transaction("/send-money", {
                    "sender_user_id": user_id,
                    "receiver_user_id": receiver.strip(),
                    "transaction_amount": round(amount,2),
                    "note": note.strip() or None,
                    "idempotency_key": str(uuid.uuid4()),
                }, f"৳{amount:,.2f} sent successfully.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Mobile Recharge":
        number = st.text_input("Mobile Number", placeholder="01XXXXXXXXX")
        operator = st.selectbox("Operator", ["Grameenphone","Robi","Banglalink","Airtel","Teletalk"])
        amount = st.number_input("Amount (৳)", min_value=10.0, max_value=5000.0, value=100.0, step=10.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Recharge", use_container_width=True):
            run_transaction("/mobile-recharge", {
                "user_id": user_id, "mobile_number": number.strip(),
                "operator": operator, "amount": round(amount,2),
                "idempotency_key": str(uuid.uuid4()),
            }, f"৳{amount:,.2f} mobile recharge successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Cash Out":
        atm = st.selectbox("ATM", ["Codex ATM • Branch 01","Codex ATM • Branch 02","Codex ATM • Express"])
        amount = st.number_input("Amount (৳)", min_value=100.0, max_value=50000.0, value=500.0, step=100.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Cash Out", use_container_width=True):
            run_transaction("/cash-out", {
                "user_id": user_id, "amount": round(amount,2), "atm": atm,
                "idempotency_key": str(uuid.uuid4()),
            }, f"৳{amount:,.2f} cash out successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Pay Bill":
        category = st.selectbox("Bill Type", ["Electricity","Gas","Water"])
        providers = {
            "Electricity":["DESCO","DPDC","Palli Bidyut"],
            "Gas":["Titas Gas"],
            "Water":["Dhaka WASA","Chattogram WASA"]
        }
        provider = st.selectbox("Provider", providers[category])
        customer = st.text_input("Customer / Meter ID")
        amount = st.number_input("Amount (৳)", min_value=1.0, max_value=100000.0, value=500.0, step=50.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Pay Bill", use_container_width=True):
            run_transaction("/pay-bill", {
                "user_id": user_id, "category": category, "provider": provider,
                "customer_id": customer.strip(), "amount": round(amount,2),
                "idempotency_key": str(uuid.uuid4()),
            }, f"{category} bill payment of ৳{amount:,.2f} successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Make Payment":
        merchant_id = st.text_input("Merchant ID", placeholder="M-1024")
        merchant_name = st.text_input("Merchant Name", placeholder="Demo Store")
        amount = st.number_input("Amount (৳)", min_value=1.0, max_value=1000000.0, value=300.0, step=50.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Pay Now", use_container_width=True):
            run_transaction("/merchant-payment", {
                "user_id": user_id, "merchant_id": merchant_id.strip(),
                "merchant_name": merchant_name.strip(), "amount": round(amount,2),
                "idempotency_key": str(uuid.uuid4()),
            }, f"Payment of ৳{amount:,.2f} successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "QR Payment":
        target = st.text_input("QR / User ID", placeholder="2048 or MERCHANT-01")
        amount = st.number_input("Amount (৳)", min_value=1.0, max_value=1000000.0, value=250.0, step=50.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Scan & Pay", use_container_width=True):
            run_transaction("/qr-payment", {
                "user_id": user_id, "qr_target": target.strip(),
                "amount": round(amount,2), "idempotency_key": str(uuid.uuid4()),
            }, f"QR payment of ৳{amount:,.2f} successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "E-Toll":
        vehicle = st.text_input("Vehicle Number", placeholder="DHAKA-METRO-GA-12-3456")
        plaza = st.selectbox("Toll Plaza", ["Padma Bridge","Dhaka Elevated Expressway","Demo Toll Plaza"])
        amount = st.number_input("Amount (৳)", min_value=20.0, max_value=5000.0, value=100.0, step=20.0)
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Pay E-Toll", use_container_width=True):
            run_transaction("/e-toll", {
                "user_id": user_id, "vehicle": vehicle.strip(), "plaza": plaza,
                "amount": round(amount,2), "idempotency_key": str(uuid.uuid4()),
            }, f"E-Toll payment of ৳{amount:,.2f} successful.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Balance Inquiry":
        bal = balance_for(user_id)
        st.markdown(f"""
        <div class='balance' style='margin-top:8px'>
            <div class='balance-label'>Available Balance</div>
            <div class='balance-amount'>৳{bal['current_available_balance']:,.2f}</div>
            <div class='status-line'>Account Status:
                <span class='status-pill'>{esc(bal.get('status','ACTIVE'))}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif name in ("Mini Statement","Transaction History"):
        limit = 5 if name == "Mini Statement" else 50
        data, err = api("GET", f"/transaction-history/{user_id}?limit={limit}&offset=0")
        if err:
            error_box(err)
        elif data:
            df = pd.DataFrame(data)
            df["transaction_type"] = df["transaction_type"].str.replace("_"," ").str.title()
            keep = ["recorded_at","transaction_type","transaction_amount","transaction_status","description"]
            keep = [x for x in keep if x in df.columns]
            st.dataframe(df[keep], use_container_width=True, hide_index=True)
        else:
            st.info("No transactions yet.")

    elif name == "Cards":
        st.session_state.tab = "Account"
        st.session_state.service = None
        st.rerun()

    elif name == "Add Money":
        st.info("Demo feature: add money is shown as a wallet service, but no real bank rail is connected.")

    elif name == "Card Top-up":
        cards_data, err = api("GET", f"/cards/{user_id}")
        if err or not cards_data:
            error_box("No demo card found for this account.")
        else:
            card = cards_data[0]
            if card["blocked"]:
                error_box("This card is blocked. Unblock it first to top up your wallet.")
            else:
                st.markdown(f"""
                <div class='balance' style='margin-top:8px;margin-bottom:16px'>
                    <div class='balance-label'>Card Balance • •••• {esc(card['last4'])}</div>
                    <div class='balance-amount'>৳{card['card_balance']:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)
                amount = st.number_input(
                    "Amount (৳)", min_value=1.0,
                    max_value=float(max(card["card_balance"], 1.0)),
                    value=min(500.0, max(card["card_balance"], 1.0)), step=50.0,
                )
                st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
                if st.button("Add to Wallet", use_container_width=True):
                    run_transaction("/cards/topup", {
                        "user_id": user_id, "card_id": card["card_id"],
                        "amount": round(amount, 2),
                        "idempotency_key": str(uuid.uuid4()),
                    }, f"৳{amount:,.2f} added to your wallet from your card.")
                st.markdown("</div>", unsafe_allow_html=True)

    elif name == "Request Money":
        st.info("Opening the Requests page…")
        go_tab("Requests")

    elif name == "Help & Support":
        st.markdown("""
        **Codex Pay Demo Support**

        - Demo wallet only
        - No real bank or bKash rail is connected
        - Transactions update the local demo database
        - Sign in with your 4-digit User ID or your username, plus your password
        """)
    st.markdown("</div>", unsafe_allow_html=True)

def service_page(user):
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>Services</div>", unsafe_allow_html=True)
    st.markdown("<div class='form-sub'>Choose a service. Home shortcuts open the same service flow.</div>", unsafe_allow_html=True)

    names = [
        "Send Money","Mobile Recharge","Cash Out","Pay Bill",
        "Make Payment","QR Payment","E-Toll","Cards",
        "Balance Inquiry","Mini Statement","Transaction History","Add Money",
        "Request Money","Help & Support"
    ]
    if st.session_state.service is None:
        for row_start in range(0, len(names), 4):
            cols = st.columns(4, gap="medium")
            for col, name in zip(cols, names[row_start:row_start+4]):
                with col:
                    st.markdown("<div class='service-button'>", unsafe_allow_html=True)
                    if st.button(name, key=f"service_menu_{name}", use_container_width=True):
                        if name == "Cards":
                            go_tab("Account")
                        else:
                            st.session_state.service = name
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        if st.button("← Back to Services", key="back_services"):
            st.session_state.service = None
            st.rerun()
        service_form(st.session_state.service, user["user_id"])

def qr_page(user):
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>QR Payment</div>", unsafe_allow_html=True)
    st.markdown("<div class='form-sub'>Use the demo QR below or enter a demo receiver ID.</div>", unsafe_allow_html=True)
    # A visual demo QR is kept dependency-free so the project runs with the existing packages.
    cells=[]
    for y in range(15):
        for x in range(15):
            on=((x*7+y*11+x*y)%9)<4
            if (x<5 and y<5) or (x>=10 and y<5) or (x<5 and y>=10):
                xx=x if x<5 else x-10; yy=y if y<5 else y-10
                on=(xx in (0,4) or yy in (0,4) or (1<=xx<=3 and 1<=yy<=3))
            cells.append("" if on else "off")
    grid=''.join(f"<i class='{c}'></i>" for c in cells)
    st.markdown(f"<div class='demo-qr'><div class='demo-qr-grid'>{grid}</div></div><div class='qr-caption'>Demo QR • CODEXPAY:1024</div>", unsafe_allow_html=True)
    service_form("QR Payment", user["user_id"])

def account_page(user):
    card = demo_card(user)
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>Account</div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class='form-shell'>
        <div class='form-title'>{esc(user['full_name'])}</div>
        <div class='form-sub'>User ID: {esc(user['user_id'])} • Username: {esc(user['username'])}</div>
        {card_html(card)}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Demo Card</div>", unsafe_allow_html=True)
    if card.get("card_id") and not card.get("blocked"):
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("⬇ Add to Wallet from Card", key="card_topup_account", use_container_width=True):
            open_service("Card Top-up")
        st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("Add another demo card"):
        name = st.text_input("Card Name", value="Codex Visa")
        number = st.text_input("Card Number", placeholder="1234567812345678")
        expiry = st.text_input("Expiry", placeholder="12/30")
        st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
        if st.button("Add Card", use_container_width=True):
            data, err = api("POST","/cards/add",{
                "user_id":user["user_id"],"card_name":name.strip(),
                "card_number":number.strip(),"expiry":expiry.strip()
            })
            if err:
                error_box(err)
            else:
                success_dialog("Demo card added successfully.", None)
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Log out", key="logout", use_container_width=True):
        st.session_state.session_user = None
        st.session_state.tab = "Home"
        st.rerun()

# ---------- Requests (Request Money) ----------
def fetch_money_requests(user_id):
    data, err = api("GET", f"/money-requests/{user_id}")
    if err or not data:
        return {"incoming": [], "outgoing": []}
    return data

def pending_incoming_count(user_id):
    data = fetch_money_requests(user_id)
    return sum(1 for r in data["incoming"] if r["status"] == "pending")

def requests_page(user):
    uid = user["user_id"]
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>Requests</div>", unsafe_allow_html=True)
    st.markdown("<div class='form-sub'>Request money from another user, or respond to requests sent to you.</div>", unsafe_allow_html=True)

    st.markdown("<div class='form-shell'>", unsafe_allow_html=True)
    st.markdown("<div class='form-title' style='font-size:19px'>New Request</div>", unsafe_allow_html=True)
    payer = st.text_input("From User ID", max_chars=4, placeholder="2048", key="req_payer")
    amount = st.number_input("Amount (৳)", min_value=1.0, max_value=1000000.0, value=100.0, step=50.0, key="req_amt")
    note = st.text_input("Note (optional)", key="req_note")
    st.markdown("<div class='primary-btn'>", unsafe_allow_html=True)
    if st.button("Send Request", use_container_width=True, key="send_request_btn"):
        if len(payer.strip()) != 4:
            error_box("Enter a valid 4-digit User ID.")
        else:
            data, err = api("POST", "/money-requests", {
                "requester_user_id": uid,
                "payer_user_id": payer.strip(),
                "amount": round(amount, 2),
                "note": note.strip() or None,
            })
            if err:
                error_box(err)
            else:
                success_dialog(f"Request for ৳{amount:,.2f} sent to User {payer.strip()}.", None)
    st.markdown("</div></div>", unsafe_allow_html=True)

    reqs = fetch_money_requests(uid)

    st.markdown("<div class='section-title'>Requests Waiting on You</div>", unsafe_allow_html=True)
    pending_incoming = [r for r in reqs["incoming"] if r["status"] == "pending"]
    if not pending_incoming:
        st.markdown("<div class='req-card'><div style='padding:22px;text-align:center;color:#747d90'>No pending requests.</div></div>", unsafe_allow_html=True)
    else:
        for r in pending_incoming:
            st.markdown(
                "<div class='req-card'><div class='req-row'>"
                "<div class='req-left'>"
                "<div class='req-icon'>♙</div>"
                "<div>"
                f"<div class='req-name'>{esc(r['requester_name'])} (User {esc(r['requester_user_id'])})</div>"
                f"<div class='req-desc'>{esc(r.get('note') or 'Requested money transfer')}</div>"
                "</div>"
                "</div>"
                f"<div class='req-amount'>৳{float(r['amount']):,.2f}</div>"
                "</div></div>",
                unsafe_allow_html=True,
            )
            bcol1, bcol2 = st.columns(2, gap="small")
            with bcol1:
                st.markdown("<div class='accept-btn-marker'></div>", unsafe_allow_html=True)
                if st.button("Accept", key=f"accept_{r['request_id']}", use_container_width=True):
                    data, err = api("POST", f"/money-requests/{r['request_id']}/accept", {"acting_user_id": uid})
                    if err:
                        error_box(err)
                    else:
                        success_dialog(f"Sent ৳{float(r['amount']):,.2f} to {r['requester_name']}.", data.get("transaction_reference_id"))
            with bcol2:
                st.markdown("<div class='reject-btn-marker'></div>", unsafe_allow_html=True)
                if st.button("Reject", key=f"reject_{r['request_id']}", use_container_width=True):
                    data, err = api("POST", f"/money-requests/{r['request_id']}/reject", {"acting_user_id": uid})
                    if err:
                        error_box(err)
                    else:
                        st.rerun()

    st.markdown("<div class='section-title'>Requests You've Sent</div>", unsafe_allow_html=True)
    if not reqs["outgoing"]:
        st.markdown("<div class='req-card'><div style='padding:22px;text-align:center;color:#747d90'>You haven't sent any requests yet.</div></div>", unsafe_allow_html=True)
    else:
        rows = []
        for r in reqs["outgoing"]:
            pill_cls = f"req-status-{r['status']}"
            rows.append(
                "<div class='req-row'>"
                "<div class='req-left'>"
                "<div class='req-icon'>♟</div>"
                "<div>"
                f"<div class='req-name'>{esc(r['payer_name'])} (User {esc(r['payer_user_id'])})</div>"
                f"<div class='req-desc'>{esc(r.get('note') or 'Money request')}</div>"
                "</div>"
                "</div>"
                "<div style='text-align:right'>"
                f"<div class='req-amount'>৳{float(r['amount']):,.2f}</div>"
                f"<span class='req-status-pill {pill_cls}'>{esc(r['status'].title())}</span>"
                "</div>"
                "</div>"
            )
        st.markdown("<div class='req-card'>" + "".join(rows) + "</div>", unsafe_allow_html=True)

# ---------- Transactions (full history page) ----------
def transactions_page(user):
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>Transactions</div>", unsafe_allow_html=True)
    st.markdown("<div class='form-sub'>Your full transaction history, most recent first.</div>", unsafe_allow_html=True)
    data, err = api("GET", f"/transaction-history/{user['user_id']}?limit=100&offset=0")
    if err:
        error_box(err)
    elif not data:
        st.markdown("<div class='tx-card'><div style='padding:25px;text-align:center;color:#747d90'>No transactions yet.</div></div>", unsafe_allow_html=True)
    else:
        df = pd.DataFrame(data)
        df["transaction_type"] = df["transaction_type"].str.replace("_"," ").str.title()
        keep = ["recorded_at","transaction_type","transaction_amount","transaction_status","description"]
        keep = [x for x in keep if x in df.columns]
        st.dataframe(df[keep], use_container_width=True, hide_index=True)

# ---------- Support ----------
def support_page(user):
    st.markdown("<div class='section-title' style='font-size:29px;margin-top:4px'>Support</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='form-shell'>
        <div class='form-title' style='font-size:19px'>Codex Pay Demo Support</div>
        <div class='form-sub' style='margin-bottom:0'>
        &bull; Demo wallet only, no real bank or mobile-money rail is connected<br>
        &bull; Transactions update the local demo database<br>
        &bull; Sign in with your 4-digit User ID or username, plus your password<br>
        &bull; For account issues, use Cards or Transactions to review your activity
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------- App ----------
if st.session_state.session_user is None:
    login()
else:
    user = st.session_state.session_user

    if st.session_state.sidebar_open:
        side_ratio, main_ratio = 0.22, 0.78
    else:
        side_ratio, main_ratio = 0.045, 0.955

    side_col, main_col = st.columns([side_ratio, main_ratio], gap="small")

    with side_col:
        if st.session_state.sidebar_open:
            st.markdown("<div class='sidebar-marker'></div>", unsafe_allow_html=True)
            sidebar(st.session_state.tab)
        else:
            st.markdown("<div class='sidebar-collapsed-marker'></div>", unsafe_allow_html=True)
            if st.button("☰", key="reopen_sidebar", use_container_width=True):
                st.session_state.sidebar_open = True
                st.rerun()

    with main_col:
        st.markdown("<div class='main-marker'></div>", unsafe_allow_html=True)
        header_bar(user)

        if st.session_state.tab == "Home":
            home(user)
        elif st.session_state.tab == "QR Payment":
            qr_page(user)
        elif st.session_state.tab == "Service":
            service_page(user)
        elif st.session_state.tab == "Requests":
            requests_page(user)
        elif st.session_state.tab == "Transactions":
            transactions_page(user)
        elif st.session_state.tab == "Support":
            support_page(user)
        else:
            account_page(user)

    # ---------- Floating promo button (bottom-right) ----------
    # Cycles through every promo*.png found next to app.py (promo.png,
    # promo2.png, promo3.png, ...), fading from one to the next in order
    # and looping back to the first — pure CSS, no JS needed. Only the
    # files that actually exist are shown, in that same numeric order.
    _promo_files = [p for p in ("promo.png", "promo2.png", "promo3.png") if os.path.exists(p)]
    if _promo_files:
        _promo_slides_b64 = [get_base64_image(p) for p in _promo_files]
        _n = len(_promo_slides_b64)
        # Size the panel to match the first slide's own proportions so the
        # box exactly hugs the image — with a mismatched box, object-fit:
        # contain leaves transparent letterbox gaps, and during the
        # crossfade the next/previous slide shows through those gaps,
        # which looks like the animation "leaking" outside the picture.
        try:
            from PIL import Image
            with Image.open(_promo_files[0]) as _im:
                _panel_w, _panel_h = _im.size
        except Exception:
            _panel_w, _panel_h = 4, 5  # fallback to the old ratio
        _cycle_seconds = 4.0 * _n          # ~4s of visible time per slide
        _slide_pct = 100 / _n              # each slide's share of the shared keyframe
        _fade_pct = _slide_pct * 0.12      # small crossfade in/out within that share

        _slides_html = "".join(
            f'<img class="promo-slide" src="data:image/png;base64,{b64}" '
            f'style="animation-delay:{-(i * _cycle_seconds / _n):.3f}s">'
            for i, b64 in enumerate(_promo_slides_b64)
        )

        if _n > 1:
            _slide_css = f"""
            .promo-fab-panel img.promo-slide {{
                position: absolute; top: 0; left: 0;
                width: 100%; height: 100%;
                object-fit: contain; display: block;
                opacity: 0;
                animation-name: promo-cycle;
                animation-duration: {_cycle_seconds}s;
                animation-timing-function: ease-in-out;
                animation-iteration-count: infinite;
            }}
            @keyframes promo-cycle {{
                0% {{ opacity: 0; }}
                {_fade_pct:.3f}% {{ opacity: 1; }}
                {(_slide_pct - _fade_pct):.3f}% {{ opacity: 1; }}
                {_slide_pct:.3f}% {{ opacity: 0; }}
                100% {{ opacity: 0; }}
            }}
            """
        else:
            # Only one promo image found — behave exactly like the
            # original single-image panel, no animation needed.
            _slide_css = """
            .promo-fab-panel img.promo-slide {
                position: static; width: 100%; display: block;
            }
            """

        st.markdown(f"""
        <style>
        .promo-fab-wrap {{
            position: fixed;
            right: 28px;
            bottom: 28px;
            z-index: 9999;
        }}
        #promo-toggle {{
            display: none;
        }}
        .promo-fab-label {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 58px;
            height: 58px;
            border-radius: 50%;
            background: linear-gradient(135deg,#E91E63,#7B1FA2);
            box-shadow: 0 10px 26px rgba(123,31,162,.35);
            cursor: pointer;
            font-size: 26px;
            color: #fff;
            transition: transform .25s ease;
        }}
        .promo-fab-label:hover {{
            transform: scale(1.08);
        }}
        .promo-fab-panel {{
            position: absolute;
            right: 0;
            bottom: 72px;
            width: 300px;
            aspect-ratio: {_panel_w} / {_panel_h};
            border-radius: 18px;
            overflow: hidden;
            opacity: 0;
            padding: 0;
            margin: 0;
            background: transparent;
            border: none;
            box-shadow: 0 18px 40px rgba(0,0,0,.25);
            transform: translateY(16px) scale(.96);
            pointer-events: none;
            transition: opacity .28s ease, transform .28s ease;
        }}
        {_slide_css}
        .promo-fab-panel::after {{
            content: "";
            position: absolute;
            top: 0;
            left: -150%;
            width: 55%;
            height: 100%;
            background: linear-gradient(115deg, transparent, rgba(255,255,255,.45), transparent);
            transform: skewX(-20deg);
            pointer-events: none;
            z-index: 2;
        }}
        #promo-toggle:checked ~ .promo-fab-panel {{
            opacity: 1;
            transform: translateY(0) scale(1);
            pointer-events: auto;
        }}
        #promo-toggle:checked ~ .promo-fab-panel::after {{
            animation: promo-shimmer 2.6s ease-in-out infinite;
        }}
        #promo-toggle:checked ~ .promo-fab-label {{
            transform: rotate(45deg);
        }}
        @keyframes promo-shimmer {{
            0%   {{ left: -150%; }}
            55%  {{ left: 150%; }}
            100% {{ left: 150%; }}
        }}
        </style>

        <div class="promo-fab-wrap">
            <input type="checkbox" id="promo-toggle">
            <label for="promo-toggle" class="promo-fab-label">🏷️</label>
            <div class="promo-fab-panel">{_slides_html}</div>
        </div>
        """, unsafe_allow_html=True)