# ATAOL AI Techs - Birlesik Outreach Otomasyonu

ATAOL AI Techs catisi altinda hem StrategyThrust hem ActLedger'i tek bir mailde tanitan B2B outreach otomasyon sistemi.

## Architecture

```
ataol-outreach/
  config.py              - Config (env vars, branding, iki platform URL'leri)
  models.py              - Lead + Email dataclass'lari
  database.py            - SQLite CRUD (WAL mode, FK)
  localization.py        - 50+ ulke dil/timezone mapping
  pipeline/
    research.py          - Gemini + Google Search ile firma bulma (TR+EN sorgular)
    scraper.py           - Website scraping, email bulma, decision maker tespiti
    analyzer.py          - Cift platform analiz (stratejik + operasyonel pain points)
    email_generator.py   - Cift platform HTML email sablonu + Gemini ile uretim
    email_validator.py   - KEP filtresi, MX kontrolu, email skorlama
    sender.py            - Gmail API ile gonderim (timezone-aware, rate limited)
    scheduler.py         - Cron zamanlayici
    followup.py          - 4. ve 7. gun otomatik follow-up
  gmail_auth/            - OAuth2 credentials + token
  dashboard/             - Flask web panel
  scripts/
    daily_pipeline.py    - Gunluk otomasyon runner
    run_pipeline.py      - Manuel pipeline
    sync_to_github.py    - Dashboard Gist sync
    setup_gmail.py       - Gmail OAuth kurulumu
  notifications/         - Email bildirimleri
  .github/workflows/     - GitHub Actions (daily + send)
```

## Platforms

1. **StrategyThrust** - Stratejik karar destek: 72 saat, 1/150 maliyet
2. **ActLedger** - Performans yonetimi: 15 sektor, 7800+ KPI, 5 katmanli cerceve

## Key Config

- Sender: sertacgul@strategythrust.com (Gmail OAuth2)
- Gemini: gemini-2.5-flash
- DB: data/ataol.db (SQLite)
- Max emails/day: 25 (local) / 70 (GitHub Actions)

## Email Structure (tek mail, iki platform)

1. ATAOL AI Techs header
2. Firmaya ozel giris + ATAOL tanitim
3. On degerlendirme (sektor, asama, olcek)
4. Stratejik zorluklar (kirmizi sidebar)
5. Operasyonel zorluklar (turuncu sidebar)
6. StrategyThrust bolumu (mavi border)
7. ActLedger bolumu (cyan border) + kampanya bilgisi
8. Inovasyon & dunya ilkleri (koyu arka plan)
9. Gorusme planla (mailto butonlari)
10. Footer (iki platform linki + LinkedIn)

## ActLedger Kampanya

- 3 aylik lisans: +1 ay ucretsiz
- Yillik lisans: %15 indirim

## Rules

- Em-dash ve en-dash kullanma, sadece kisa hyphen (-)
- Mail metninde AI/yapay zeka ifadesi KULLANILMAZ
- McKinsey kurumsal ciddiyetinde ton
- 72 saat ve 1/150 fiyat sadece 1'er kez
- Fiyat belirtme (rakam yok), avantaj olarak sun
- .env, gmail_auth/ dosyalari ASLA commit etme
