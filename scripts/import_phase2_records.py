"""Import verified GOV.UK appointments, historical UK Gazette people, and Sri Lanka Gazette records."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "GazetteRegistry/1.0 (+https://gazetteregistry.com; records research)"
TODAY = date.today().isoformat()

GOVUK_APPOINTMENTS = [
    {
        "url": "https://www.gov.uk/government/news/new-chairman-appointed-to-the-disclosure-and-barring-service",
        "document_id": "DOC-GB-0201",
        "record_uid": "GB-2026-APPT-004",
        "title": "Julian Blazeby appointed Chairman of the Disclosure and Barring Service",
        "published": "2026-11-24",
        "person_id": "person:gb:julian-blazeby",
        "canonical_name": "Julian Blazeby",
        "published_name": "Julian Blazeby",
        "position": "Chairman, Disclosure and Barring Service",
        "variant": None,
        "org_id": "org:gb:disclosure-and-barring-service",
        "org_name": "Disclosure and Barring Service",
    },
    {
        "url": "https://www.gov.uk/government/news/trustee-appointed-to-the-science-museum-group",
        "document_id": "DOC-GB-0202",
        "record_uid": "GB-2026-APPT-005",
        "title": "Professor Danielle George CBE appointed Trustee to the Science Museum Group",
        "published": "2026-11-24",
        "person_id": "person:gb:danielle-george",
        "canonical_name": "Danielle George",
        "published_name": "Professor Danielle George CBE",
        "position": "Trustee, Science Museum Group",
        "variant": "Professor Danielle George CBE",
        "org_id": "org:gb:science-museum-group",
        "org_name": "Science Museum Group",
    },
    {
        "url": "https://www.gov.uk/government/news/hmcts-appoints-new-non-executive-director--2",
        "document_id": "DOC-GB-0203",
        "record_uid": "GB-2026-APPT-006",
        "title": "Ravi Mahendra appointed Non-Executive Director at HM Courts and Tribunals Service",
        "published": "2026-11-20",
        "person_id": "person:gb:ravi-mahendra",
        "canonical_name": "Ravi Mahendra",
        "published_name": "Ravi Mahendra",
        "position": "Non-Executive Director and ARAC Member, HMCTS Board",
        "variant": None,
        "org_id": "org:gb:hm-courts-and-tribunals-service",
        "org_name": "HM Courts and Tribunals Service",
    },
    {
        "url": "https://www.gov.uk/government/news/member-reappointed-to-the-treasure-valuation-committee",
        "document_id": "DOC-GB-0204",
        "record_uid": "GB-2026-APPT-007",
        "title": "Professor Leslie Webster reappointed to the Treasure Valuation Committee",
        "published": "2026-11-20",
        "person_id": "person:gb:leslie-webster",
        "canonical_name": "Leslie Webster",
        "published_name": "Professor Leslie Webster",
        "position": "Member, Treasure Valuation Committee",
        "variant": "Professor Leslie Webster",
        "org_id": "org:gb:treasure-valuation-committee",
        "org_name": "Treasure Valuation Committee",
    },
    {
        "url": "https://www.gov.uk/government/news/home-secretary-welcomes-new-migration-advisory-committee-chair",
        "document_id": "DOC-GB-0205",
        "record_uid": "GB-2026-APPT-008",
        "title": "Professor Jackline Wahba OBE appointed Chair of the Migration Advisory Committee",
        "published": "2026-11-19",
        "person_id": "person:gb:jackline-wahba",
        "canonical_name": "Jackline Wahba",
        "published_name": "Professor Jackline Wahba OBE",
        "position": "Chair, Migration Advisory Committee",
        "variant": "Professor Jackline Wahba OBE",
        "org_id": "org:gb:migration-advisory-committee",
        "org_name": "Migration Advisory Committee",
    },
    {
        "url": "https://www.gov.uk/government/news/new-chair-appointed-to-the-law-commission-of-england-and-wales",
        "document_id": "DOC-GB-0206",
        "record_uid": "GB-2026-APPT-009",
        "title": "Mr Justice Pepperall appointed Chair of the Law Commission of England and Wales",
        "published": "2026-11-18",
        "person_id": "person:gb:mr-justice-pepperall",
        "canonical_name": "Mr Justice Pepperall",
        "published_name": "The Honourable Mr Justice Pepperall",
        "position": "Chair, Law Commission for England and Wales",
        "variant": "The Honourable Mr Justice Pepperall",
        "org_id": "org:gb:law-commission-of-england-and-wales",
        "org_name": "Law Commission of England and Wales",
    },
    {
        "url": "https://www.gov.uk/government/news/alan-milburn-appointed-chair-of-the-new-youth-opportunities-unit",
        "document_id": "DOC-GB-0207",
        "record_uid": "GB-2026-APPT-010",
        "title": "Alan Milburn appointed Chair of the Youth Opportunities Unit",
        "published": "2026-11-17",
        "person_id": "person:gb:alan-milburn",
        "canonical_name": "Alan Milburn",
        "published_name": "Alan Milburn",
        "position": "Chair, Youth Opportunities Unit",
        "variant": None,
        "org_id": "org:gb:youth-opportunities-unit",
        "org_name": "Youth Opportunities Unit",
    },
    {
        "url": "https://www.gov.uk/government/news/reviewer-of-state-threats-and-terrorism-legislation-appointed",
        "document_id": "DOC-GB-0208",
        "record_uid": "GB-2026-APPT-011",
        "title": "Rupert Jones appointed Independent Reviewer of Terrorism and State Threats Legislation",
        "published": "2026-11-16",
        "person_id": "person:gb:rupert-jones",
        "canonical_name": "Rupert Jones",
        "published_name": "Rupert Jones",
        "position": "Independent Reviewer of Terrorism Legislation and State Threats Legislation",
        "variant": None,
        "org_id": "org:gb:home-office",
        "org_name": "Home Office",
    },
    {
        "url": "https://www.gov.uk/government/news/reappointment-of-a-member-to-the-parole-board--2",
        "document_id": "DOC-GB-0209",
        "record_uid": "GB-2026-APPT-012",
        "title": "Shellie Adams reappointed as a member of the Parole Board",
        "published": "2026-11-16",
        "person_id": "person:gb:shellie-adams",
        "canonical_name": "Shellie Adams",
        "published_name": "Shellie Adams",
        "position": "Member, Parole Board",
        "variant": None,
        "org_id": "org:gb:parole-board",
        "org_name": "Parole Board",
    },
    {
        "url": "https://www.gov.uk/government/news/shriti-vadera-appointed-as-external-adviser-to-the-chancellor",
        "document_id": "DOC-GB-0210",
        "record_uid": "GB-2026-APPT-013",
        "title": "Shriti Vadera appointed External Adviser to the Chancellor",
        "published": "2026-11-06",
        "person_id": "person:gb:shriti-vadera",
        "canonical_name": "Shriti Vadera",
        "published_name": "Shriti Vadera",
        "position": "External Adviser on G20 and international innovative finance issues",
        "variant": None,
        "org_id": "org:gb:hm-treasury",
        "org_name": "HM Treasury",
    },
    {
        "url": "https://www.gov.uk/government/news/new-chair-appointed-to-the-national-savings-and-investments-board",
        "document_id": "DOC-GB-0211",
        "record_uid": "GB-2026-APPT-014",
        "title": "Luke Jensen appointed Chair of the National Savings and Investments Board",
        "published": "2026-11-04",
        "person_id": "person:gb:luke-jensen",
        "canonical_name": "Luke Jensen",
        "published_name": "Luke Jensen",
        "position": "Chair, National Savings and Investments (NS&I) Board",
        "variant": None,
        "org_id": "org:gb:national-savings-and-investments",
        "org_name": "National Savings and Investments",
    },
    {
        "url": "https://www.gov.uk/government/news/dr-ewan-kirk-appointed-mods-director-innovation",
        "document_id": "DOC-GB-0212",
        "record_uid": "GB-2026-APPT-015",
        "title": "Dr Ewan Kirk appointed MOD Director Innovation",
        "published": "2026-11-04",
        "person_id": "person:gb:ewan-kirk",
        "canonical_name": "Ewan Kirk",
        "published_name": "Dr Ewan Kirk",
        "position": "Director Innovation, Ministry of Defence",
        "variant": "Dr Ewan Kirk",
        "org_id": "org:gb:ministry-of-defence",
        "org_name": "Ministry of Defence",
    },
    {
        "url": "https://www.gov.uk/government/news/raj-jethwa-reappointed-as-a-member-of-the-prison-service-pay-review-body",
        "document_id": "DOC-GB-0213",
        "record_uid": "GB-2026-APPT-016",
        "title": "Raj Jethwa reappointed as a member of the Prison Service Pay Review Body",
        "published": "2026-11-03",
        "person_id": "person:gb:raj-jethwa",
        "canonical_name": "Raj Jethwa",
        "published_name": "Raj Jethwa",
        "position": "Member, Prison Service Pay Review Body",
        "variant": None,
        "org_id": "org:gb:prison-service-pay-review-body",
        "org_name": "Prison Service Pay Review Body",
    },
    {
        "url": "https://www.gov.uk/government/news/army-trustee-appointed-to-the-imperial-war-museum-board",
        "document_id": "DOC-GB-0214",
        "record_uid": "GB-2026-APPT-017",
        "title": "Major-General Lisa Keetley appointed Army Trustee to the Imperial War Museum Board",
        "published": "2026-10-30",
        "person_id": "person:gb:lisa-keetley",
        "canonical_name": "Lisa Keetley",
        "published_name": "Major-General Lisa Keetley",
        "position": "Trustee, Imperial War Museum Board",
        "variant": "Major-General Lisa Keetley",
        "org_id": "org:gb:imperial-war-museum",
        "org_name": "Imperial War Museum",
    },
    {
        "url": "https://www.gov.uk/government/news/sir-nicholas-coleridge-reappointed-as-the-chair-of-historic-royal-palaces",
        "document_id": "DOC-GB-0215",
        "record_uid": "GB-2026-APPT-018",
        "title": "Sir Nicholas Coleridge CBE reappointed as Chair of Historic Royal Palaces",
        "published": "2026-10-30",
        "person_id": "person:gb:nicholas-coleridge",
        "canonical_name": "Nicholas Coleridge",
        "published_name": "Sir Nicholas Coleridge CBE",
        "position": "Chair, Historic Royal Palaces",
        "variant": "Sir Nicholas Coleridge CBE",
        "org_id": "org:gb:historic-royal-palaces",
        "org_name": "Historic Royal Palaces",
    },
]

GB_HISTORICAL_RECORDS = [
    {
        "uid": "GB-1914-29002-APPT-002",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Lieutenant-Colonel Charles J. Sackville West appointed General Staff Officer, 1st Grade",
        "page": 2,
        "excerpt": "Lieutenant-Colonel The Honourable Charles J. Sackville West, The King's Royal Rifle Corps. Dated 30th September, 1914.",
        "person_id": "person:gb:charles-j-sackville-west",
        "canonical_name": "Charles J. Sackville West",
        "published_name": "Charles J. Sackville West",
        "position": "General Staff Officer, 1st Grade (Lieutenant-Colonel)",
        "position_kind": "appointment",
        "variant": "The Honourable Charles J. Sackville West",
        "org_id": "org:gb:kings-royal-rifle-corps",
        "org_name": "The King's Royal Rifle Corps",
        "keywords": ["appointment", "military", "General Staff"],
    },
    {
        "uid": "GB-1914-29002-APPT-003",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Captain William L. O. Twiss appointed General Staff Officer, 2nd Grade",
        "page": 2,
        "excerpt": "Captain William L. O. Twiss, 9th Gurkha Rifles, Indian Army. Dated 30th Septem- ber, 1914.",
        "person_id": "person:gb:william-l-o-twiss",
        "canonical_name": "William L. O. Twiss",
        "published_name": "William L. O. Twiss",
        "position": "General Staff Officer, 2nd Grade (Captain, 9th Gurkha Rifles)",
        "position_kind": "appointment",
        "variant": None,
        "org_id": "org:gb:indian-army",
        "org_name": "Indian Army",
        "keywords": ["appointment", "military", "Indian Army"],
    },
    {
        "uid": "GB-1914-29002-APPT-004",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Major Berkeley Vincent appointed General Staff Officer, 2nd Grade",
        "page": 2,
        "excerpt": "Major Berkeley Vincent, 6th (Innis- killing) Dragoons. Dated 30th September, 1914.",
        "person_id": "person:gb:berkeley-vincent",
        "canonical_name": "Berkeley Vincent",
        "published_name": "Berkeley Vincent",
        "position": "General Staff Officer, 2nd Grade (Major)",
        "position_kind": "appointment",
        "variant": None,
        "org_id": "org:gb:inniskilling-dragoons",
        "org_name": "6th (Inniskilling) Dragoons",
        "keywords": ["appointment", "military", "General Staff"],
    },
    {
        "uid": "GB-1914-29002-APPT-005",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Major James R. E. Charles appointed General Staff Officer, 2nd Grade",
        "page": 2,
        "excerpt": "Major James R. E. Charles, D.S.O., Royal Engineers. Dated 30th September, 1914.",
        "person_id": "person:gb:james-r-e-charles",
        "canonical_name": "James R. E. Charles",
        "published_name": "James R. E. Charles",
        "position": "General Staff Officer, 2nd Grade (Major)",
        "position_kind": "appointment",
        "variant": "James R. E. Charles, D.S.O.",
        "org_id": "org:gb:royal-engineers",
        "org_name": "Royal Engineers",
        "keywords": ["appointment", "military", "Royal Engineers"],
    },
    {
        "uid": "GB-1914-29002-APPT-006",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Major-General Henry M. Lawson appointed Assistant to the Chief of the Imperial General Staff",
        "page": 3,
        "excerpt": "Major-General Henry M. Lawson, C.B., from Commanding the troops in Guernsey and Alderney, in succession to Major- General Sir F. S. Robb, K.C.V.O., C.B. Dated 21st November, 1914.",
        "person_id": "person:gb:henry-m-lawson",
        "canonical_name": "Henry M. Lawson",
        "published_name": "Henry M. Lawson",
        "position": "Assistant to the Chief of the Imperial General Staff (Major-General)",
        "position_kind": "appointment",
        "variant": "Henry M. Lawson, C.B.",
        "org_id": "org:gb:war-office",
        "org_name": "War Office",
        "keywords": ["appointment", "military", "War Office"],
    },
    {
        "uid": "GB-1914-29002-APPT-007",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Honorary Brigadier-General John F. Burn-Murdoch appointed Commandant, Remount Depot",
        "page": 3,
        "excerpt": "Honorary Brigadier-General John F. Burn-Murdoch, C.B., retired pay. Dated 10th December, 1914.",
        "person_id": "person:gb:john-f-burn-murdoch",
        "canonical_name": "John F. Burn-Murdoch",
        "published_name": "John F. Burn-Murdoch",
        "position": "Commandant, Remount Depot (Honorary Brigadier-General)",
        "position_kind": "appointment",
        "variant": "John F. Burn-Murdoch, C.B.",
        "org_id": "org:gb:war-office",
        "org_name": "War Office",
        "keywords": ["appointment", "military", "Remount Depot"],
    },
    {
        "uid": "GB-1915-29131-APPT-003",
        "issue_id": "GB-1915-29131",
        "record_type": "commissioning",
        "title": "Frederick Edward Sanders Pulling commissioned Second Lieutenant, Hampshire Regiment",
        "page": 13,
        "excerpt": "6th (Duke of Connaught's Own) Battalion, The Hampshire Regiment; Frederick Ed- ward Sanders Pulling to be Second Lieu- tenant. Dated 22nd March, 1915.",
        "person_id": "person:gb:frederick-edward-sanders-pulling",
        "canonical_name": "Frederick Edward Sanders Pulling",
        "published_name": "Frederick Edward Sanders Pulling",
        "position": "Second Lieutenant, 6th Battalion, The Hampshire Regiment",
        "position_kind": "commissioning",
        "variant": None,
        "org_id": "org:gb:hampshire-regiment",
        "org_name": "The Hampshire Regiment",
        "keywords": ["commissioning", "military", "Territorial Force"],
    },
    {
        "uid": "GB-1915-29131-APPT-004",
        "issue_id": "GB-1915-29131",
        "record_type": "commissioning",
        "title": "Wilfred Batten Lewis Trotter, M.D., commissioned Captain, 3rd London General Hospital",
        "page": 15,
        "excerpt": "3rd London General Hospital; Wilfred Batten Lewis Trotter, M.D., to be Captain, whose services will be available on mobilisation. Dated 22nd March, 1915.",
        "person_id": "person:gb:wilfred-batten-lewis-trotter",
        "canonical_name": "Wilfred Batten Lewis Trotter",
        "published_name": "Wilfred Batten Lewis Trotter, M.D.",
        "position": "Captain, 3rd London General Hospital (Territorial Force)",
        "position_kind": "commissioning",
        "variant": "Wilfred Batten Lewis Trotter, M.D.",
        "org_id": "org:gb:3rd-london-general-hospital",
        "org_name": "3rd London General Hospital",
        "keywords": ["commissioning", "medical", "Territorial Force"],
    },
]

LK_PEOPLE_POSITIONS = [
    {
        "uid": "LK-2026-2504-APPT-001",
        "issue_id": "LK-2026-2504",
        "page": "LK-2026-2504-PAGE-051",
        "title": "A. L. K. Wijemannage, Director General, Department of Meteorology",
        "needle": "A. L. K. Wijemannage,",
        "person_id": "person:lk:a-l-k-wijemannage",
        "canonical_name": "A. L. K. Wijemannage",
        "published_name": "A. L. K. Wijemannage",
        "position": "Director General, Department of Meteorology",
        "position_kind": "professional",
        "variant": None,
        "org_id": "org:lk:department-of-meteorology",
        "org_name": "Department of Meteorology",
    },
    {
        "uid": "LK-2026-2504-APPT-002",
        "issue_id": "LK-2026-2504",
        "page": "LK-2026-2504-PAGE-061",
        "title": "M. K. S. R. D. Samarasinghe, Director General of Export Agriculture",
        "needle": "M. K. S. R. D. Samarasinghe,",
        "person_id": "person:lk:m-k-s-r-d-samarasinghe",
        "canonical_name": "M. K. S. R. D. Samarasinghe",
        "published_name": "M. K. S. R. D. Samarasinghe",
        "position": "Director General of Export Agriculture",
        "position_kind": "professional",
        "variant": None,
        "org_id": "org:lk:department-of-export-agriculture",
        "org_name": "Department of Export Agriculture",
    },
    {
        "uid": "LK-2026-2505-APPT-001",
        "issue_id": "LK-2026-2505",
        "page": "LK-2026-2505-PAGE-010",
        "title": "Dr. T. M. N. P. Tennakoon, Registrar (Acting), Homoeopathic Medical Council",
        "needle": "Dr. T.M.N.P. Tennakoon,",
        "person_id": "person:lk:t-m-n-p-tennakoon",
        "canonical_name": "T. M. N. P. Tennakoon",
        "published_name": "Dr. T.M.N.P. Tennakoon",
        "position": "Registrar (Acting), Homoeopathic Medical Council",
        "position_kind": "acting",
        "variant": "Dr. T.M.N.P. Tennakoon",
        "org_id": "org:lk:homoeopathic-medical-council",
        "org_name": "Homoeopathic Medical Council",
    },
    {
        "uid": "LK-2026-2505-APPT-002",
        "issue_id": "LK-2026-2505",
        "page": "LK-2026-2505-PAGE-028",
        "title": "Eng. W. R. N. R. Premachandra, Director General of Buildings",
        "needle": "Eng. W. R. N. R. Premachandra,",
        "person_id": "person:lk:w-r-n-r-premachandra",
        "canonical_name": "W. R. N. R. Premachandra",
        "published_name": "Eng. W. R. N. R. Premachandra",
        "position": "Director General of Buildings, Department of Buildings",
        "position_kind": "professional",
        "variant": "Eng. W. R. N. R. Premachandra",
        "org_id": "org:lk:department-of-buildings",
        "org_name": "Department of Buildings",
    },
    {
        "uid": "LK-2026-2506-APPT-001",
        "issue_id": "LK-2026-2506",
        "page": "LK-2026-2506-PAGE-012",
        "title": "W. W. S. Mangala, Secretary, Ministry of Ports and Civil Aviation",
        "needle": "W. W. S. Mangala,",
        "person_id": "person:lk:w-w-s-mangala",
        "canonical_name": "W. W. S. Mangala",
        "published_name": "W. W. S. Mangala",
        "position": "Secretary, Ministry of Ports and Civil Aviation",
        "position_kind": "professional",
        "variant": None,
        "org_id": "org:lk:ministry-of-ports-and-civil-aviation",
        "org_name": "Ministry of Ports and Civil Aviation",
    },
    {
        "uid": "LK-2026-2506-APPT-002",
        "issue_id": "LK-2026-2506",
        "page": "LK-2026-2506-PAGE-066",
        "title": "D. K. Wijesinghe, Secretary, Audit Service Commission",
        "needle": "D. K. Wijesinghe,",
        "person_id": "person:lk:d-k-wijesinghe",
        "canonical_name": "D. K. Wijesinghe",
        "published_name": "D. K. Wijesinghe",
        "position": "Secretary, Audit Service Commission",
        "position_kind": "professional",
        "variant": None,
        "org_id": "org:lk:audit-service-commission",
        "org_name": "Audit Service Commission",
    },
]

LK_NOTICES = [
    {
        "uid": "LK-2026-2502-NOTC-002",
        "issue_id": "LK-2026-2502",
        "page": "LK-2026-2502-PAGE-012",
        "title": "Open Competitive Examination for Recruitment to Posts of Transport Costing Officer Grade III, Sri Lanka Railway Department",
        "category": "professional",
        "needle": "SRI LANKA RAILWAY DEPARTMENT",
        "org_id": "org:lk:sri-lanka-railway-department",
        "org_name": "Sri Lanka Railway Department",
    },
    {
        "uid": "LK-2026-2504-NOTC-002",
        "issue_id": "LK-2026-2504",
        "page": "LK-2026-2504-PAGE-007",
        "title": "Recruitment to the Post of Reserve Assistant Superintendent of Police (IT, Engineering, Architecture), Sri Lanka Police",
        "category": "professional",
        "needle": "SRI LANKA POLICE",
        "org_id": "org:lk:sri-lanka-police",
        "org_name": "Sri Lanka Police",
    },
    {
        "uid": "LK-2026-2504-NOTC-003",
        "issue_id": "LK-2026-2504",
        "page": "LK-2026-2504-PAGE-050",
        "title": "Amendment to Open Competitive Examination for Sri Lanka Inland Revenue Service Grade III - 2026",
        "category": "professional",
        "needle": "SRI LANKA INLAND REVENUE SERVICE 2026",
        "org_id": "org:lk:public-service-commission",
        "org_name": "Public Service Commission",
    },
    {
        "uid": "LK-2026-2505-NOTC-002",
        "issue_id": "LK-2026-2505",
        "page": "LK-2026-2505-PAGE-009",
        "title": "Recruitment to the Post of Homoeopathic Medical Officer, Homoeopathic Medical Council",
        "category": "professional",
        "needle": "HOMOEOPATHIC MEDICAL COUNCIL",
        "org_id": "org:lk:homoeopathic-medical-council",
        "org_name": "Homoeopathic Medical Council",
    },
    {
        "uid": "LK-2026-2506-NOTC-002",
        "issue_id": "LK-2026-2506",
        "page": "LK-2026-2506-PAGE-053",
        "title": "Open Competitive Examination for Electro-Medical Technician Grade III (64 Vacancies), Ministry of Health and Mass Media",
        "category": "professional",
        "needle": "MINISTRY OF HEALTH AND MASS MEDIA",
        "org_id": "org:lk:ministry-of-health-and-mass-media",
        "org_name": "Ministry of Health and Mass Media",
    },
    {
        "uid": "LK-2026-2506-NOTC-003",
        "issue_id": "LK-2026-2506",
        "page": "LK-2026-2506-PAGE-061",
        "title": "Open Competitive Examination for Recruitment of 244 Audit Officers, Sri Lanka State Audit Service - 2026",
        "category": "professional",
        "needle": "AUDIT SERVICE COMMISSION",
        "org_id": "org:lk:audit-service-commission",
        "org_name": "Audit Service Commission",
    },
]


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_of(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return normalise(html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw)))


def read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: row[key])
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert(rows: list[dict], key: str, item: dict) -> list[dict]:
    return [row for row in rows if row[key] != item[key]] + [item]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            time.sleep(0.3)
            return data
        except OSError as exc:
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def extract_govuk_body(raw: str) -> str:
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            structured = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(structured, dict) and structured.get("articleBody"):
            return text_of(structured["articleBody"])
    raise RuntimeError("articleBody not found")


def import_govuk(gb: dict[str, list[dict]]) -> int:
    added = 0
    for item in GOVUK_APPOINTMENTS:
        raw_bytes = fetch(item["url"])
        body = extract_govuk_body(raw_bytes.decode("utf-8", "replace"))
        text = normalise(f"{item['title']} | {body}")
        source_sha = hashlib.sha256(raw_bytes).hexdigest()
        excerpt = text[:400]

        gb["documents"] = upsert(
            gb["documents"],
            "document_id",
            {
                "document_id": item["document_id"],
                "country_code": "GB",
                "source_id": "gb-govuk-news",
                "official_url": item["url"],
                "retrieved_at": TODAY,
                "content_type": "text/html",
                "language": "en",
                "title": item["title"],
                "publisher": "GOV.UK",
                "publication_date": item["published"],
                "source_bytes": len(raw_bytes),
                "source_sha256": source_sha,
                "checksum_scope": "source_response",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
        )
        gb["records"] = upsert(
            gb["records"],
            "uid",
            {
                "uid": item["record_uid"],
                "record_type": "appointment",
                "title": item["title"],
                "summary": None,
                "issue_id": None,
                "publication_date": item["published"],
                "language": "en",
                "issuing_organisation_name": item["org_name"],
                "people": [
                    {
                        "person_id": item["person_id"],
                        "published_name": item["published_name"],
                        "position": item["position"],
                        "position_kind": "appointment",
                        "organisation_ids": [item["org_id"]],
                    }
                ],
                "organisation_ids": [item["org_id"]],
                "location": "United Kingdom",
                "keywords": ["appointment", "public office"],
                "tender": None,
                "regulation": None,
                "notice": None,
                "source": {
                    "kind": "html",
                    "pdf_page": None,
                    "printed_page": None,
                    "document_id": item["document_id"],
                    "excerpt": excerpt,
                    "official_url": item["url"],
                    "sha256": source_sha,
                    "checksum_scope": "source_response",
                    "retrieved_at": TODAY,
                },
            },
        )
        gb["people"] = upsert(
            gb["people"],
            "person_id",
            {
                "person_id": item["person_id"],
                "country_code": "GB",
                "canonical_name": item["canonical_name"],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Identity reviewed against the official appointment announcement {item['url']} published {item['published']} and retrieved {TODAY}.",
            },
        )
        gb["organisations"] = upsert(
            gb["organisations"],
            "organisation_id",
            {
                "organisation_id": item["org_id"],
                "country_code": "GB",
                "name": item["org_name"],
                "type": "government_body",
                "aliases": [],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Named in official announcement {item['url']} published {item['published']}.",
            },
        )
        if item["variant"]:
            variant_id = f"VAR-GB-{item['record_uid'].rsplit('-', 1)[-1]}"
            gb["variants"] = upsert(
                gb["variants"],
                "variant_id",
                {
                    "variant_id": variant_id,
                    "person_id": item["person_id"],
                    "name": item["variant"],
                    "verification": "operator_verified",
                    "basis": f"Name form published in {item['url']} ({item['record_uid']}).",
                    "reviewed_at": TODAY,
                    "source_record_uids": [item["record_uid"]],
                },
            )
        added += 1
        print(f"GOV.UK {item['record_uid']}: {item['canonical_name']}")
    return added


def import_gb_historical(gb: dict[str, list[dict]]) -> int:
    issues = {
        "GB-1914-29002": {
            "dir": DATA / "gb" / "1914" / "1914-12-08-29002",
            "pdf": ROOT / "raw" / "Gazette-1914-12-08-S.pdf",
        },
        "GB-1915-29131": {
            "dir": DATA / "gb" / "1915" / "1915-04-13-29131",
            "pdf": ROOT / "raw" / "Gazette-1915-04-13-S.pdf",
        },
    }
    issue_data = {iid: json.loads((p["dir"] / "issue.json").read_text(encoding="utf-8")) for iid, p in issues.items()}
    texts_by_issue = {
        iid: {
            json.loads(line)["uid"]: json.loads(line)["text"]
            for line in gzip.open(p["dir"] / "text.jsonl.gz", "rt", encoding="utf-8")
        }
        for iid, p in issues.items()
    }
    pdf_shas = {iid: hashlib.sha256(p["pdf"].read_bytes()).hexdigest() for iid, p in issues.items()}
    added = 0
    for item in GB_HISTORICAL_RECORDS:
        iid = item["issue_id"]
        page_uid = f"{iid}-PAGE-{item['page']:03d}"
        if normalise(item["excerpt"]) not in normalise(texts_by_issue[iid][page_uid]):
            raise RuntimeError(f"{item['uid']}: excerpt not found in {page_uid}")
        issue = issue_data[iid]
        gb["records"] = upsert(
            gb["records"],
            "uid",
            {
                "uid": item["uid"],
                "record_type": item["record_type"],
                "title": item["title"],
                "summary": None,
                "issue_id": iid,
                "publication_date": issue["publication_date"],
                "language": "en",
                "issuing_organisation_name": "War Office",
                "people": [
                    {
                        "person_id": item["person_id"],
                        "published_name": item["published_name"],
                        "position": item["position"],
                        "position_kind": item["position_kind"],
                        "organisation_ids": [item["org_id"]],
                    }
                ],
                "organisation_ids": [item["org_id"]],
                "location": "United Kingdom",
                "keywords": item["keywords"],
                "tender": None,
                "regulation": None,
                "notice": None,
                "source": {
                    "kind": "pdf",
                    "pdf_page": item["page"],
                    "printed_page": None,
                    "document_id": None,
                    "excerpt": item["excerpt"],
                    "official_url": issue["source_url"],
                    "sha256": pdf_shas[iid],
                    "checksum_scope": "original_source",
                    "retrieved_at": "2026-11-18",
                },
            },
        )
        gb["people"] = upsert(
            gb["people"],
            "person_id",
            {
                "person_id": item["person_id"],
                "country_code": "GB",
                "canonical_name": item["canonical_name"],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Identity reviewed against the official Gazette {iid}, page {item['page']}, published {issue['publication_date']}.",
            },
        )
        gb["organisations"] = upsert(
            gb["organisations"],
            "organisation_id",
            {
                "organisation_id": item["org_id"],
                "country_code": "GB",
                "name": item["org_name"],
                "type": "government_body",
                "aliases": [],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Named in the official Gazette {iid}, page {item['page']}, published {issue['publication_date']}.",
            },
        )
        if item["variant"]:
            variant_id = f"VAR-GB-HIST-{item['uid'].rsplit('-', 1)[-1]}-{item['issue_id'][-5:]}"
            gb["variants"] = upsert(
                gb["variants"],
                "variant_id",
                {
                    "variant_id": variant_id,
                    "person_id": item["person_id"],
                    "name": item["variant"],
                    "verification": "operator_verified",
                    "basis": f"Name form printed in the cited Gazette notice {item['uid']}.",
                    "reviewed_at": TODAY,
                    "source_record_uids": [item["uid"]],
                },
            )
        added += 1
        print(f"GB-HIST {item['uid']}: {item['canonical_name']}")
    return added


def import_lk(lk: dict[str, list[dict]]) -> int:
    lk_dir = DATA / "lk"
    sources = {row["issue_id"]: row for row in read_ndjson(lk_dir / "sources" / "sources.ndjson")}
    issue_cache: dict[str, tuple[dict, dict, dict]] = {}
    for dir_path in sorted((lk_dir / "2026").iterdir()):
        if not dir_path.is_dir():
            continue
        issue = json.loads((dir_path / "issue.json").read_text(encoding="utf-8"))
        pages = {row["uid"]: row for row in read_ndjson(dir_path / "pages.ndjson")}
        texts = {
            json.loads(line)["uid"]: json.loads(line)["text"]
            for line in gzip.open(dir_path / "text.jsonl.gz", "rt", encoding="utf-8")
        }
        issue_cache[issue["issue_id"]] = (issue, pages, texts)

    lk["records"] = [row for row in lk["records"] if "-POS-" not in row["uid"]]
    lk["variants"] = [row for row in lk["variants"] if "POS" not in row["variant_id"]]
    added = 0
    for item in LK_PEOPLE_POSITIONS:
        issue, pages, texts = issue_cache[item["issue_id"]]
        page = pages[item["page"]]
        text = texts[item["page"]]
        idx = text.find(item["needle"])
        if idx == -1:
            raise RuntimeError(f"{item['uid']}: needle {item['needle']} not in {item['page']}")
        start = max(0, idx - 140)
        excerpt = normalise(text[start : idx + 200])
        source = sources[item["issue_id"]]

        lk["records"] = upsert(
            lk["records"],
            "uid",
            {
                "uid": item["uid"],
                "record_type": "professional_position",
                "title": item["title"],
                "summary": None,
                "issue_id": item["issue_id"],
                "publication_date": issue["publication_date"],
                "language": "en",
                "issuing_organisation_name": item["org_name"],
                "people": [
                    {
                        "person_id": item["person_id"],
                        "published_name": item["published_name"],
                        "position": item["position"],
                        "position_kind": item["position_kind"],
                        "organisation_ids": [item["org_id"]],
                    }
                ],
                "organisation_ids": [item["org_id"]],
                "location": "Sri Lanka",
                "keywords": ["gazette", "official signatory", "public service"],
                "tender": None,
                "regulation": None,
                "notice": None,
                "source": {
                    "kind": "pdf",
                    "pdf_page": page["physical_pdf_page"],
                    "printed_page": page["printed_page"],
                    "document_id": None,
                    "excerpt": excerpt,
                    "official_url": issue["source_url"],
                    "sha256": source["sha256"],
                    "checksum_scope": "original_source",
                    "retrieved_at": None,
                },
            },
        )
        lk["people"] = upsert(
            lk["people"],
            "person_id",
            {
                "person_id": item["person_id"],
                "country_code": "LK",
                "canonical_name": item["canonical_name"],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Identity reviewed against tracked Sri Lanka Gazette {issue['gazette_no']} ({issue['publication_date']}), page {page['printed_page'] or page['physical_pdf_page']}.",
            },
        )
        lk["organisations"] = upsert(
            lk["organisations"],
            "organisation_id",
            {
                "organisation_id": item["org_id"],
                "country_code": "LK",
                "name": item["org_name"],
                "type": "government_body",
                "aliases": [],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Named in tracked Sri Lanka Gazette {issue['gazette_no']} ({issue['publication_date']}), page {page['printed_page'] or page['physical_pdf_page']}.",
            },
        )
        if item["variant"]:
            variant_id = f"VAR-LK-{item['uid'].replace('-', '')}"
            lk["variants"] = upsert(
                lk["variants"],
                "variant_id",
                {
                    "variant_id": variant_id,
                    "person_id": item["person_id"],
                    "name": item["variant"],
                    "verification": "operator_verified",
                    "basis": f"Name form printed in tracked Sri Lanka Gazette notice {item['uid']}.",
                    "reviewed_at": TODAY,
                    "source_record_uids": [item["uid"]],
                },
            )
        added += 1
        print(f"LK-POS {item['uid']}: {item['canonical_name']}")

    for item in LK_NOTICES:
        issue, pages, texts = issue_cache[item["issue_id"]]
        page = pages[item["page"]]
        text = texts[item["page"]]
        idx = text.find(item["needle"])
        if idx == -1:
            raise RuntimeError(f"{item['uid']}: needle {item['needle']} not in {item['page']}")
        excerpt = normalise(text[idx : idx + 320])
        source = sources[item["issue_id"]]

        lk["records"] = upsert(
            lk["records"],
            "uid",
            {
                "uid": item["uid"],
                "record_type": "public_notice",
                "title": item["title"],
                "summary": None,
                "issue_id": item["issue_id"],
                "publication_date": issue["publication_date"],
                "language": "en",
                "issuing_organisation_name": item["org_name"],
                "people": [],
                "organisation_ids": [item["org_id"]],
                "location": "Sri Lanka",
                "keywords": ["gazette", "public service", "examination"],
                "tender": None,
                "regulation": None,
                "notice": {"category": item["category"]},
                "source": {
                    "kind": "pdf",
                    "pdf_page": page["physical_pdf_page"],
                    "printed_page": page["printed_page"],
                    "document_id": None,
                    "excerpt": excerpt,
                    "official_url": issue["source_url"],
                    "sha256": source["sha256"],
                    "checksum_scope": "original_source",
                    "retrieved_at": None,
                },
            },
        )
        lk["organisations"] = upsert(
            lk["organisations"],
            "organisation_id",
            {
                "organisation_id": item["org_id"],
                "country_code": "LK",
                "name": item["org_name"],
                "type": "government_body",
                "aliases": [],
                "identity_status": "operator_verified",
                "verified_at": TODAY,
                "basis": f"Named in tracked Sri Lanka Gazette {issue['gazette_no']} ({issue['publication_date']}), page {page['printed_page'] or page['physical_pdf_page']}.",
            },
        )
        added += 1
        print(f"LK-NOTC {item['uid']}: {item['title'][:65]}")
    return added


def main() -> int:
    gb_dir = DATA / "gb"
    gb = {
        "records": read_ndjson(gb_dir / "records" / "records.ndjson"),
        "documents": read_ndjson(gb_dir / "sources" / "documents.ndjson"),
        "organisations": read_ndjson(gb_dir / "entities" / "organisations.ndjson"),
        "people": read_ndjson(gb_dir / "entities" / "people.ndjson"),
        "variants": read_ndjson(gb_dir / "entities" / "name-variants.ndjson"),
    }
    lk_dir = DATA / "lk"
    lk = {
        "records": read_ndjson(lk_dir / "records" / "records.ndjson"),
        "organisations": read_ndjson(lk_dir / "entities" / "organisations.ndjson"),
        "people": read_ndjson(lk_dir / "entities" / "people.ndjson"),
        "variants": read_ndjson(lk_dir / "entities" / "name-variants.ndjson"),
    }

    added_govuk = import_govuk(gb)
    added_hist = import_gb_historical(gb)
    added_lk = import_lk(lk)

    write_ndjson(gb_dir / "records" / "records.ndjson", gb["records"], "uid")
    write_ndjson(gb_dir / "sources" / "documents.ndjson", gb["documents"], "document_id")
    write_ndjson(gb_dir / "entities" / "organisations.ndjson", gb["organisations"], "organisation_id")
    write_ndjson(gb_dir / "entities" / "people.ndjson", gb["people"], "person_id")
    write_ndjson(gb_dir / "entities" / "name-variants.ndjson", gb["variants"], "variant_id")

    write_ndjson(lk_dir / "records" / "records.ndjson", lk["records"], "uid")
    write_ndjson(lk_dir / "entities" / "organisations.ndjson", lk["organisations"], "organisation_id")
    write_ndjson(lk_dir / "entities" / "people.ndjson", lk["people"], "person_id")
    write_ndjson(lk_dir / "entities" / "name-variants.ndjson", lk["variants"], "variant_id")

    print(f"DONE: govuk={added_govuk}, gb_hist={added_hist}, lk={added_lk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
