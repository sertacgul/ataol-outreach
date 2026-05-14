# Multi-Source Contact Enrichment

**Date:** 2026-05-14
**Status:** Approved

## Problem

Mevcut sistem tek bir Gemini cagrisiyla (find_contact_with_gemini) LinkedIn, Crunchbase ve website'i ayni anda arastirmaya calisiyor. Pratikte tek bir prompt'la hepsini derinlemesine yapmasi zor - karar verici isim/email bulma orani dusuk kaliyor.

## Decision Summary

| Karar | Secim |
|-------|-------|
| Kaynak onceligi | LinkedIn ayri cagri, Crunchbase + website tek cagri (C) |
| LinkedIn derinligi | Isim + unvan + LinkedIn URL + kisi ozeti (C) |
| DB saklama | leads tablosuna yeni kolonlar (A) |
| Fallback stratejisi | Bulunamazsa needs_manual_review, email uretme (B) |
| Maliyet optimizasyonu | Website scrape'ten kisisel email bulunursa enrichment atla (B) |
| Mimari yaklasim | Ayri contact_enrichment.py, scraper icinden cagirilir (3) |

## Data Flow

```
scrape_company(website)
  +-- Website scrape (mevcut: homepage + /contact + /about)
  +-- Email extraction + validation (mevcut)
  +-- Kisisel email bulundu mu?
  |   +-- EVET -> mevcut akis, enrichment atla
  |   +-- HAYIR -> enrich_contact(website, language)
  |       +-- Adim 1: search_linkedin(domain)
  |       |   -> Gemini + Google Search, sadece LinkedIn'e odakli
  |       |   -> Cikti: isim, unvan, linkedin_url, bio
  |       +-- Adim 2: search_crunchbase_website(domain, language)
  |       |   -> Gemini + Google Search, Crunchbase + sirket about sayfasi
  |       |   -> Cikti: isim, unvan (LinkedIn'den bulunamadiysa)
  |       +-- Sonuclari birlestir (LinkedIn oncelikli)
  |       +-- Isim bulunduysa -> pattern guessing + SMTP (mevcut)
  |       +-- Hicbir sey bulunamadiysa -> status = "needs_manual_review"
  +-- Return: emails, best_email, decision_maker, linkedin_url, bio
```

"Kisisel email bulundu mu?" kontrolu: info@, contact@, hello@ gibi generic olanlar sayilmaz - sadece ad.soyad@ veya ad@ formundaki emailler "kisisel" kabul edilir.

## Gemini Prompts

### LinkedIn aramasi (search_linkedin)

```
Bu sirketin ust duzey karar vericisini LinkedIn'de bul: {domain}

ARAMA: LinkedIn'de "{domain}" veya "{company_name}" sirketindeki
CEO, Founder, CTO, Managing Director, Genel Mudur, Kurucu ara.

ONCELIK: CEO/Founder > CTO/COO > Managing Director > VP > Director

DONDUR:
{"name": "Ad Soyad", "title": "CEO",
 "linkedin_url": "https://linkedin.com/in/...",
 "bio": "Kisa ozet - gecmis deneyim, uzmanlik alani (max 2 cumle)"}

Bulamazsan tum alanlari bos birak.
```

### Crunchbase + website aramasi (search_crunchbase_website)

```
Bu sirketin karar vericisini bul: {domain}

KAYNAK 1: Crunchbase, Bloomberg, PitchBook'ta "{company_name}" kurucu/CEO
KAYNAK 2: Sirketin kendi about/team sayfasi
KAYNAK 3: Turkce firmalar icin kariyer.net, sikayetvar, startups.watch

DONDUR:
{"name": "Ad Soyad", "title": "CEO"}

Bulamazsan tum alanlari bos birak.
```

Her iki cagri da google_search tool'u ile yapilir.

## DB Changes

### Yeni kolonlar (leads tablosu)

```sql
ALTER TABLE leads ADD COLUMN decision_maker_linkedin TEXT DEFAULT '';
ALTER TABLE leads ADD COLUMN decision_maker_bio TEXT DEFAULT '';
```

### Yeni status

`needs_manual_review` - enrichment dahil hicbir kaynaktan karar verici bulunamayan lead'ler. Bu status'taki lead'ler icin email uretilmez. email_generator.py bu status'u atlar.

## Module Structure

### pipeline/contact_enrichment.py

```python
def search_linkedin(domain, company_name, language) -> dict:
    """LinkedIn-odakli Gemini + Google Search cagrisi.
    Return: {name, title, linkedin_url, bio}"""

def search_crunchbase_website(domain, company_name, language) -> dict:
    """Crunchbase + sirket about sayfasi Gemini cagrisi.
    Return: {name, title}"""

def merge_results(linkedin_result, crunchbase_result) -> dict:
    """LinkedIn oncelikli birlestirme.
    - LinkedIn isim varsa onu kullan
    - LinkedIn bossa Crunchbase'den al
    - linkedin_url ve bio sadece LinkedIn'den gelir"""

def enrich_contact(domain, company_name, language="tr") -> dict:
    """Ana giris noktasi. scraper.py'den cagirilir.
    1. search_linkedin()
    2. search_crunchbase_website()
    3. merge_results()
    4. Return: {name, title, linkedin_url, bio, source}"""
```

### scraper.py entegrasyonu

- `scrape_company()` icinde mevcut `find_contact_with_gemini()` cagrisi kaldirilir
- Yerine: website scrape sonrasi kisisel email kontrolu, bulunamadiysa `enrich_contact()` cagirilir
- `enrich_contact()` sonuclari result dict'e merge edilir
- Isim bulunduysa mevcut `find_personal_email_by_pattern()` calisir
- Hala email yoksa `needs_manual_review`

### run_scraping() update

- UPDATE query'sine `decision_maker_linkedin` ve `decision_maker_bio` eklenir
- Enrichment sonrasi kisisel email bulunamadiysa `status = 'needs_manual_review'` set edilir

## Cost Impact

- Mevcut: lead basina 1 Gemini cagrisi (contact search)
- Yeni: kisisel email bulunamayan lead'ler icin +2 Gemini cagrisi (LinkedIn + Crunchbase)
- Website scrape'ten kisisel email bulunan lead'ler icin maliyet degismez
- Tahmini: lead'lerin ~%60-70'inde enrichment gerekecek -> gunluk ~50-60 ek Gemini cagrisi
