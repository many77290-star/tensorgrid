#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TensorGrid — générateur du feed de données Bittensor subnets.

Source (publique, sans clé, déjà éprouvée en prod via kairos_subnets.py) :
  - CoinGecko  /coins/markets?category=bittensor-subnets  -> prix USD, market cap,
    volume, perf 24h/7j/30j de CHAQUE token alpha de subnet (symbole snXX).
  - CoinGecko  /coins/markets?ids=bittensor               -> prix + perf TAO (référence).

Ce script N'UTILISE AUCUN SECRET : uniquement des endpoints publics.
Il est donc sûr d'être publié/poussé dans le repo public.

Modes :
   python refresh_feed.py            -> écrit feeds/*.json (local, pour dev)
   python refresh_feed.py --publish  -> idem + git add feeds/ + commit + push (cron machine)

Sorties (dans feeds/, à la racine du repo — racine GitHub Pages) :
   subnets.json  : jeu de données complet normalisé
   meta.json     : métadonnées API (version, refresh, endpoints, rate-limit)
"""
import sys, os, json, time, datetime, urllib.request, urllib.error, subprocess

ROOT   = os.path.dirname(os.path.abspath(__file__))
SFEEDS = os.path.join(ROOT, "feeds")
HIST   = os.path.join(SFEEDS, "history")

GLITCH_CAP = 3000.0   # filtre anti-glitch CoinGecko (mes crons font pareil)
UA = {"User-Agent": "TensorGrid/1.0 (+" + "https://many77290-star.github.io/tensorgrid" + "; requests: github.com/many77290-star/tensorgrid/issues)"}


def http_json(url, tries=3, timeout=25):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print(f"  [warn] échec {url} : {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))
    return None


def fnum(x):
    """Coerce numérique robuste (None-safe)."""
    try:
        v = float(x)
        return v
    except (TypeError, ValueError):
        return None


def num_or_none(x):
    v = fnum(x)
    return None if v is None else v


def build():
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # TAO (référence) — prix + perf 24h/7j/30j dans un appel unique.
    tao_row = http_json("https://api.coingecko.com/api/v3/coins/markets"
                        "?ids=bittensor&vs_currency=usd"
                        "&price_change_percentage=24h,7d,30d")
    tao = None
    if tao_row:
        c = tao_row[0]
        tao = {
            "usd": num_or_none(c.get("current_price")),
            "var24h": num_or_none(c.get("price_change_percentage_24h_in_currency")),
            "var7d": num_or_none(c.get("price_change_percentage_7d_in_currency")),
            "var30d": num_or_none(c.get("price_change_percentage_30d_in_currency")),
            "market_cap_usd": num_or_none(c.get("market_cap")),
            "total_volume_usd": num_or_none(c.get("total_volume")),
        }

    # Univers des subnets — tous les tokens alpha de la catégorie.
    rows = http_json("https://api.coingecko.com/api/v3/coins/markets"
                     "?vs_currency=usd&category=bittensor-subnets"
                     "&order=market_cap_desc&per_page=250"
                     "&price_change_percentage=24h,7d,30d")

    if not rows:
        print("[ABORT] CoinGecko indisponible — feed non généré (retry au prochain passage).",
              file=sys.stderr)
        return None

    subnets = []
    for c in rows:
        v30 = num_or_none(c.get("price_change_percentage_30d_in_currency"))
        # filtre anti-glitch : perf 30j aberrante -> on la neutralise mais on garde le token
        glitch = v30 is not None and abs(v30) > GLITCH_CAP
        subnets.append({
            "symbol": (c.get("symbol") or "").lower(),
            "name": c.get("name"),
            "id": c.get("id"),
            "usd": num_or_none(c.get("current_price")),
            "var24h": num_or_none(c.get("price_change_percentage_24h_in_currency")),
            "var7d": num_or_none(c.get("price_change_percentage_7d_in_currency")),
            "var30d": None if glitch else v30,
            "var30d_glitched": glitch,
            "market_cap_usd": num_or_none(c.get("market_cap")),
            "total_volume_usd": num_or_none(c.get("total_volume")),
            "circulating_supply": num_or_none(c.get("circulating_supply")),
            "ath_usd": num_or_none(c.get("ath")),
            "high_24h": num_or_none(c.get("high_24h")),
            "low_24h": num_or_none(c.get("low_24h")),
        })

    # rangs + signal alpha-vs-TAO (la métrique qui décide, reprise du pipeline éprouvé).
    by_mcap = sorted(range(len(subnets)), key=lambda i: -(subnets[i]["market_cap_usd"] or 0))
    mcap_rank = {idx: r + 1 for r, idx in enumerate(by_mcap)}
    for i in range(len(subnets)):
        subnets[i]["rank_by_mcap"] = mcap_rank[i]

    valid_30 = [s["var30d"] for s in subnets
                if s["var30d"] is not None and abs(s["var30d"]) <= GLITCH_CAP]
    sorted30 = sorted((i for i in range(len(subnets))
                       if subnets[i]["var30d"] is not None and abs(subnets[i]["var30d"]) <= GLITCH_CAP),
                      key=lambda i: -subnets[i]["var30d"])
    perf_rank = {idx: r + 1 for r, idx in enumerate(sorted30)}
    for i in range(len(subnets)):
        s = subnets[i]
        s["rank_by_30d"] = perf_rank.get(i)
        s["beats_tao_30d"] = (s["var30d"] is not None and tao is not None
                              and tao.get("var30d") is not None
                              and s["var30d"] > tao["var30d"])

    universe = {
        "count": len(subnets),
        "with_30d_data": len(valid_30),
        "median_30d": (sorted(valid_30)[len(valid_30) // 2] if valid_30 else None),
        "beat_tao_count": sum(1 for s in subnets if s["beats_tao_30d"]),
    }
    if universe["with_30d_data"]:
        universe["beat_tao_pct"] = round(universe["beat_tao_count"] / universe["with_30d_data"] * 100, 1)
    else:
        universe["beat_tao_pct"] = None

    data = {
        "asset": "bittensor-subnets",
        "version": "1.0",
        "generated_at": now_iso,
        "source": "CoinGecko category=bittensor-subnets (public, keyless)",
        "tao": tao,
        "universe": universe,
        "subnets": subnets,
    }

    os.makedirs(SFEEDS, exist_ok=True)
    os.makedirs(HIST, exist_ok=True)
    with open(os.path.join(SFEEDS, "subnets.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    meta = {
        "product": "TensorGrid",
        "product_url": "https://many77290-star.github.io/tensorgrid",
        "api_base": "https://many77290-star.github.io/tensorgrid/feeds",
        "version": "1.0",
        "refresh_minutes": 15,
        "rate_limit": {"free": "10 req/min", "standard": "300 req/min", "pro": "3000 req/min"},
        "endpoints": {
            "subnets": "/feeds/subnets.json",
            "meta": "/feeds/meta.json",
            "history": "/feeds/history/snapshot-YYYYMMDD.json",
        },
        "licensed_under": "TensorGrid Data License 1.0 (see /docs)",
        "contact": "github.com/many77290-star/tensorgrid/issues?labels=access",
        "generated_at": now_iso,
    }
    with open(os.path.join(SFEEDS, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # snapshot historique quotidien (alimente la valeur historique payante).
    day = now_iso[:10]
    snap = os.path.join(HIST, f"snapshot-{day}.json")
    light = {
        "date": day,
        "tao_usd": (tao or {}).get("usd"),
        "tao_30d": (tao or {}).get("var30d"),
        "count": universe["count"],
        "median_30d": universe["median_30d"],
        "beat_tao_count": universe["beat_tao_count"],
        "top5_mcap": [{"symbol": s["symbol"], "market_cap_usd": s["market_cap_usd"]}
                      for s in subnets if s["market_cap_usd"]][:5],
    }
    with open(snap, "w", encoding="utf-8") as f:
        json.dump(light, f, ensure_ascii=False, indent=2)

    print(f"[OK] feed généré : {len(subnets)} subnets, TAO={tao.get('usd') if tao else '?'}$, "
          f"médiane 30j={universe['median_30d']}%, {universe['beat_tao_count']} battent TAO.")

    # rétention historique : garde 400 derniers snapshots (limites de repo)
    snaps = sorted([n for n in os.listdir(HIST) if n.startswith("snapshot-")])
    for n in snaps[:-400]:
        os.remove(os.path.join(HIST, n))

    if "--publish" in sys.argv:
        publish()
    return data


def publish():
    """git add feeds/ + commit + push (idempotent). Sûr : seul le JSON public est poussé."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cmds = [
        ["git", "add", "feeds"],
        ["git", "-c", "user.name=KAIROS Agent",
         "-c", "user.email=kairos@nousresearch.com",
         "commit", "-m", f"feeds: refresh {stamp}", "--", "feeds"],
        ["git", "push"],
    ]
    for c in cmds:
        p = subprocess.run(c, cwd=ROOT, capture_output=True, text=True)
        tag = " ".join(c[1:3])
        if p.returncode != 0 and "nothing to commit" not in p.stdout.lower() and "Everything up-to-date" not in p.stdout:
            print(f"[publish] {tag} : rc={p.returncode}", file=sys.stderr)
            if p.stderr:
                print(f"  {p.stderr.strip()}", file=sys.stderr)
    print("[publish] feeds publié (GitHub Pages redéploiera automatiquement).")


if __name__ == "__main__":
    build()
