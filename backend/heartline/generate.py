"""Builds a synthetic population with linked families and writes it to SQLite.

Nothing here is real patient data. The population is shaped to be plausible for Abu Dhabi:
multi-generation Emirati families with relatives in the same health system, expatriate
households whose relatives mostly live abroad, and single expatriate workers.

Familial hypercholesterolaemia (FH) is assigned to founders at a set prevalence and then
inherited: each carrier parent passes the variant to each child with probability 0.5.

Run: python -m heartline.generate
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from .config import DATA, DB_PATH, LDL_P95_ADULT, LDL_P95_CHILD, PREMATURE_AGE, REF_DATE, SEED

rng = np.random.default_rng(SEED)

EMIRATI_M = ["Mohammed", "Ahmed", "Khalid", "Saeed", "Rashid", "Hamad", "Sultan", "Abdullah", "Omar", "Saif",
             "Majid", "Faisal", "Hamdan", "Mansour", "Obaid", "Juma", "Ali", "Yousef", "Hassan", "Nasser",
             "Theyab", "Zayed", "Khalifa", "Ibrahim", "Salem", "Matar", "Butti", "Humaid"]
EMIRATI_F = ["Fatima", "Mariam", "Aisha", "Noura", "Hessa", "Shamma", "Moza", "Latifa", "Amna", "Maitha",
             "Sara", "Alyazia", "Mahra", "Reem", "Shaikha", "Hind", "Salama", "Wadima", "Asma", "Meera",
             "Ghaya", "Mouza", "Afra", "Roudha"]
EMIRATI_FAMILY = ["Al Mazrouei", "Al Dhaheri", "Al Suwaidi", "Al Shamsi", "Al Kaabi", "Al Nuaimi", "Al Mansouri",
                  "Al Hammadi", "Al Ketbi", "Al Falasi", "Al Qubaisi", "Al Ameri", "Al Marzooqi", "Al Blooshi",
                  "Al Hosani", "Al Zaabi", "Al Muhairi", "Al Romaithi", "Al Junaibi", "Al Mheiri", "Al Shehhi",
                  "Al Naqbi", "Al Tunaiji", "Al Hashmi"]

EXPAT = {
    "South Asian": (["Arjun", "Rahul", "Imran", "Vikram", "Faizan", "Anil", "Rohan", "Bilal"],
                    ["Priya", "Ananya", "Ayesha", "Divya", "Sana", "Meera", "Zainab", "Kavya"],
                    ["Nair", "Sharma", "Khan", "Menon", "Qureshi", "Iyer", "Patel", "Hussain"]),
    "Arab (other)": (["Karim", "Tarek", "Ziad", "Hani", "Samer", "Walid", "Bassam", "Rami"],
                     ["Lina", "Rana", "Dina", "Hala", "Nour", "Yasmin", "Rasha", "Mona"],
                     ["Haddad", "Khoury", "Mansour", "Saleh", "Nasser", "Aziz", "Darwish", "Fakhoury"]),
    "Filipino": (["Jose", "Mark", "Paolo", "Rafael", "Miguel", "Carlo"],
                 ["Maria", "Angelica", "Kristine", "Joy", "Patricia", "Camille"],
                 ["Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza"]),
    "Western": (["James", "Thomas", "Daniel", "Lucas", "Oliver", "Mark"],
                ["Emma", "Sophie", "Charlotte", "Laura", "Hannah", "Claire"],
                ["Smith", "Brown", "Martin", "Taylor", "Walker", "Muller"]),
}
EXPAT_WEIGHTS = {"South Asian": 0.55, "Arab (other)": 0.2, "Filipino": 0.15, "Western": 0.1}

# Founder carrier rates. Consanguinity raises the rate in Gulf families; 1 in 112 is the
# pooled Gulf estimate, the global estimate is closer to 1 in 300.
FH_RATE = {"Emirati": 1 / 100, "South Asian": 1 / 200, "Arab (other)": 1 / 150, "Filipino": 1 / 300,
           "Western": 1 / 300}

VARIANTS = [
    ("LDLR", "LDLR c.1444G>A", 0.30), ("LDLR", "LDLR c.2026delG", 0.20), ("LDLR", "LDLR c.1291G>A", 0.18),
    ("LDLR", "LDLR exon 4-6 del", 0.12), ("APOB", "APOB c.10580G>A", 0.12), ("PCSK9", "PCSK9 c.381T>A", 0.08),
]


@dataclass
class Person:
    id: int
    given: str
    family: str
    sex: str
    birth: date
    group: str
    household: int
    clan: int
    mother: int | None = None
    father: int | None = None
    death: date | None = None
    alleles: list = field(default_factory=list)  # list of variant names carried (0, 1 or 2)
    relatives_abroad: int = 0
    lang: str = "ar"


people: list[Person] = []
spouses: list[tuple[int, int]] = []
_household = [0]
_clan = [0]


def new_household() -> int:
    _household[0] += 1
    return _household[0]


def new_clan() -> int:
    _clan[0] += 1
    return _clan[0]


def rand_date(y0: int, y1: int) -> date:
    start = date(y0, 1, 1).toordinal()
    end = date(y1, 12, 31).toordinal()
    return date.fromordinal(int(rng.integers(start, end + 1)))


def age_on(p: Person, d: date) -> float:
    return (d - p.birth).days / 365.25


def pick_variant() -> str:
    w = np.array([v[2] for v in VARIANTS])
    return VARIANTS[rng.choice(len(VARIANTS), p=w / w.sum())][1]


def make(given_pool, family, sex, birth, group, household, clan, mother=None, father=None, lang="ar") -> Person:
    p = Person(len(people) + 1, str(rng.choice(given_pool)), family, sex, birth, group, household, clan,
               mother, father, lang=lang)
    people.append(p)
    return p


def founder_alleles(p: Person):
    if rng.random() < FH_RATE[p.group]:
        p.alleles = [pick_variant()]


def inherit(child: Person, mother: Person, father: Person):
    a = []
    for parent in (mother, father):
        if parent.alleles and rng.random() < 0.5:
            a.append(str(rng.choice(parent.alleles)))
    child.alleles = a


def maybe_die(p: Person):
    a = age_on(p, REF_DATE)
    if a < 45:
        return
    # Rough annual mortality rising with age; enough to make some grandparents deceased.
    risk = min(0.95, max(0.0, (a - 55) / 40))
    if rng.random() < risk * 0.7:
        lo = p.birth.year + 55
        p.death = rand_date(min(lo, REF_DATE.year - 1), REF_DATE.year - 1)


def emirati_names(sex):
    return EMIRATI_M if sex == "M" else EMIRATI_F


def make_children(mother: Person, father: Person, n: int, group: str, family: str, household: int, clan: int,
                  given_pools) -> list[Person]:
    kids = []
    for _ in range(n):
        y0 = mother.birth.year + 19
        y1 = min(mother.birth.year + 42, REF_DATE.year)
        if y0 > y1:
            break
        sex = "M" if rng.random() < 0.5 else "F"
        pool = given_pools[0] if sex == "M" else given_pools[1]
        k = make(pool, family, sex, rand_date(y0, y1), group, household, clan, mother.id, father.id, mother.lang)
        inherit(k, mother, father)
        kids.append(k)
    return kids


def emirati_clan():
    clan = new_clan()
    fam = str(rng.choice(EMIRATI_FAMILY))
    hh = new_household()
    gf = make(EMIRATI_M, fam, "M", rand_date(1938, 1962), "Emirati", hh, clan)
    gm = make(EMIRATI_F, str(rng.choice(EMIRATI_FAMILY)), "F", date.fromordinal(gf.birth.toordinal() + int(rng.integers(365 * 2, 365 * 9))),
              "Emirati", hh, clan)
    for p in (gf, gm):
        founder_alleles(p)
    spouses.append((gf.id, gm.id))
    kids = make_children(gm, gf, int(np.clip(rng.poisson(5.2), 1, 10)), "Emirati", fam, hh, clan, (EMIRATI_M, EMIRATI_F))
    for p in (gf, gm):
        maybe_die(p)
    for k in kids:
        if age_on(k, REF_DATE) < 22 or rng.random() > 0.85:
            continue
        # Spouse from outside the clan; half the time their own parents and siblings are in the system too.
        ssex = "F" if k.sex == "M" else "M"
        sfam = str(rng.choice(EMIRATI_FAMILY))
        offset = int(rng.integers(-365 * 3, 365 * 8)) if k.sex == "M" else int(rng.integers(-365 * 8, 365 * 2))
        sbirth = date.fromordinal(min(k.birth.toordinal() + offset, (REF_DATE - timedelta(days=365 * 19)).toordinal()))
        hh2 = new_household()
        if rng.random() < 0.5:
            inlaw_hh = new_household()
            ifa = make(EMIRATI_M, sfam, "M", rand_date(sbirth.year - 40, sbirth.year - 22), "Emirati", inlaw_hh, clan)
            imo = make(EMIRATI_F, str(rng.choice(EMIRATI_FAMILY)), "F",
                       rand_date(ifa.birth.year, min(ifa.birth.year + 8, sbirth.year - 19)), "Emirati", inlaw_hh, clan)
            founder_alleles(ifa)
            founder_alleles(imo)
            spouses.append((ifa.id, imo.id))
            sp = make(emirati_names(ssex), sfam, ssex, sbirth, "Emirati", hh2, clan, imo.id, ifa.id)
            inherit(sp, imo, ifa)
            for _ in range(int(rng.integers(0, 4))):
                sx = "M" if rng.random() < 0.5 else "F"
                y0, y1 = imo.birth.year + 19, min(imo.birth.year + 42, REF_DATE.year)
                if y0 <= y1:
                    sib = make(emirati_names(sx), sfam, sx, rand_date(y0, y1), "Emirati", inlaw_hh, clan, imo.id, ifa.id)
                    inherit(sib, imo, ifa)
                    maybe_die(sib)
            maybe_die(ifa)
            maybe_die(imo)
        else:
            sp = make(emirati_names(ssex), sfam, ssex, sbirth, "Emirati", hh2, clan)
            founder_alleles(sp)
        k.household = hh2
        spouses.append((k.id, sp.id))
        mother, father = (k, sp) if k.sex == "F" else (sp, k)
        gk = make_children(mother, father, int(np.clip(rng.poisson(3.6), 0, 8)), "Emirati", father.family, hh2, clan,
                           (EMIRATI_M, EMIRATI_F))
        for p in [k, sp, *gk]:
            maybe_die(p)


def expat_household():
    group = str(rng.choice(list(EXPAT_WEIGHTS), p=np.array(list(EXPAT_WEIGHTS.values()))))
    m, f, fams = EXPAT[group]
    fam = str(rng.choice(fams))
    hh = new_household()
    clan = new_clan()
    lang = "ar" if group == "Arab (other)" else "en"
    dad = make(m, fam, "M", rand_date(1966, 1996), group, hh, clan, lang=lang)
    mum = make(f, str(rng.choice(fams)), "F", rand_date(dad.birth.year - 2, min(dad.birth.year + 7, 1999)), group, hh, clan,
               lang=lang)
    for p in (dad, mum):
        founder_alleles(p)
        p.relatives_abroad = int(rng.integers(2, 7))
    spouses.append((dad.id, mum.id))
    kids = make_children(mum, dad, int(np.clip(rng.poisson(1.8), 0, 5)), group, fam, hh, clan, (m, f))
    for k in kids:
        k.relatives_abroad = int(rng.integers(3, 10))


def single_worker():
    group = str(rng.choice(list(EXPAT_WEIGHTS), p=np.array(list(EXPAT_WEIGHTS.values()))))
    m, f, fams = EXPAT[group]
    sex = "M" if rng.random() < 0.75 else "F"
    p = make(m if sex == "M" else f, str(rng.choice(fams)), sex, rand_date(1970, 2003), group, new_household(), new_clan(),
             lang="ar" if group == "Arab (other)" else "en")
    founder_alleles(p)
    p.relatives_abroad = int(rng.integers(3, 9))


# ---------------------------------------------------------------- clinical layer

def true_ldl(p: Person, a: float) -> float:
    n = len(p.alleles)
    child = a < 18
    if n >= 2:
        v = rng.normal(14.0, 2.5)
    elif n == 1:
        gene = p.alleles[0].split()[0]
        base = 5.1 if child else 6.2
        adj = {"LDLR": 0.0, "APOB": -0.9, "PCSK9": 0.4}[gene]
        v = rng.normal(base + adj, 0.9 if child else 1.2)
    else:
        v = rng.normal(2.4, 0.5) if child else rng.normal(2.9 + 0.012 * (a - 40), 0.75)
        if not child and rng.random() < 0.06:  # polygenic or lifestyle high cholesterol, the usual false alarm
            v += rng.normal(1.8, 0.5)
    return float(max(1.0, v))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def build_clinical(p: Person) -> dict:
    end = p.death or REF_DATE
    a_now = age_on(p, end)
    n = len(p.alleles)
    ldl = true_ldl(p, a_now)

    # Coronary disease: much more likely, and earlier, with FH.
    thresh = PREMATURE_AGE[p.sex]
    base = {0: 0.05 if p.sex == "M" else 0.02, 1: 0.38 if p.sex == "M" else 0.2, 2: 0.75}[min(n, 2)]
    cad_age = None
    if a_now > 30:
        span = (min(a_now, thresh) - 30) / (thresh - 30)
        if rng.random() < base * max(span, 0):
            cad_age = float(rng.uniform(30, min(a_now, thresh)))
        elif a_now > thresh and rng.random() < (0.12 if n == 0 else 0.35) * min(1, (a_now - thresh) / 20):
            cad_age = float(rng.uniform(thresh, a_now))

    # Statins: treatment is common, diagnosis of FH is not.
    statin_start = None
    intensity = None
    if a_now >= 30:
        pr = sigmoid(-3.2 + 0.05 * (a_now - 40) + 0.55 * (ldl - 3.5) + (2.5 if cad_age else 0))
        if rng.random() < pr:
            earliest = max(p.birth.year + 30, 2012)
            latest = end.year if cad_age is None else end.year
            statin_start = rand_date(min(earliest, latest), latest)
            if cad_age is not None:
                ev = p.birth + timedelta(days=int(cad_age * 365.25))
                statin_start = min(statin_start, max(ev, date(2012, 1, 1)))
            intensity = "high" if cad_age or ldl > 6 else "moderate"

    xanthoma = int(rng.random() < {0: 0.0005, 1: 0.07, 2: 0.8}[min(n, 2)] and a_now >= 18)
    arcus = int(rng.random() < {0: 0.002, 1: 0.06, 2: 0.4}[min(n, 2)] and 18 <= a_now)

    return dict(true_ldl=ldl, cad_age=cad_age, statin_start=statin_start, statin_intensity=intensity,
                xanthoma=xanthoma, arcus=arcus)


def build_labs(p: Person, c: dict) -> list[tuple]:
    end = p.death or REF_DATE
    if (end - p.birth).days < 365 * 2:
        return []
    a_now = age_on(p, end)
    if a_now < 18:
        n = 1 if rng.random() < 0.07 else 0
    else:
        lam = 2.6 if p.group == "Emirati" else 1.1
        n = int(rng.poisson(lam))
        if rng.random() < (0.18 if p.group == "Emirati" else 0.4):
            n = 0
    start = max(p.birth + timedelta(days=365 * 2), date(2016, 1, 1))
    if p.death and p.death < date(2016, 6, 1):
        return []
    out = []
    hdl_mu = 1.35 if p.sex == "F" else 1.15
    for _ in range(n):
        d = date.fromordinal(int(rng.integers(start.toordinal(), end.toordinal() + 1)))
        on = c["statin_start"] is not None and d >= c["statin_start"]
        factor = 1.0
        if on:
            factor = 1 - (rng.uniform(0.4, 0.55) if c["statin_intensity"] == "high" else rng.uniform(0.25, 0.4))
            if rng.random() < 0.25:  # not taking it
                factor = rng.uniform(0.85, 1.0)
        ldl = c["true_ldl"] * factor * float(np.exp(rng.normal(0, 0.08)))
        hdl = max(0.5, rng.normal(hdl_mu, 0.25))
        tg = float(np.exp(rng.normal(np.log(1.3), 0.4)))
        tc = ldl + hdl + tg / 2.2
        out.append((p.id, d.isoformat(), round(ldl, 2), round(tc, 2), round(hdl, 2), round(tg, 2), int(on)))
    return sorted(out, key=lambda r: r[1])


SCHEMA = """
CREATE TABLE people (
  id INTEGER PRIMARY KEY, mrn TEXT, given TEXT, family TEXT, sex TEXT, birth_date TEXT, death_date TEXT,
  nationality_group TEXT, household_id INTEGER, clan_id INTEGER, mother_id INTEGER, father_id INTEGER,
  lang TEXT, relatives_abroad INTEGER,
  statin_start TEXT, statin_intensity TEXT, cad_age REAL, xanthoma INTEGER, arcus INTEGER,
  fhx_recorded_cad INTEGER, fhx_recorded_ldl INTEGER
);
-- Ground truth lives in its own table. The API never reads it except to simulate test results
-- and to score the model against known answers.
CREATE TABLE truth (person_id INTEGER PRIMARY KEY, fh INTEGER, variant TEXT, true_ldl REAL);
CREATE TABLE spouses (a INTEGER, b INTEGER);
CREATE TABLE labs (id INTEGER PRIMARY KEY, person_id INTEGER, date TEXT, ldl REAL, tc REAL, hdl REAL, tg REAL,
  on_statin INTEGER, source TEXT DEFAULT 'history');
CREATE INDEX labs_person ON labs(person_id);
CREATE INDEX people_mother ON people(mother_id);
CREATE INDEX people_father ON people(father_id);
"""


def main(n_clans=1600, n_expat_households=5000, n_singles=7000):
    for _ in range(n_clans):
        emirati_clan()
    for _ in range(n_expat_households):
        expat_household()
    for _ in range(n_singles):
        single_worker()

    clinical = {p.id: build_clinical(p) for p in people}
    by_id = {p.id: p for p in people}
    kids_of: dict[int, list[int]] = {}
    for p in people:
        for par in (p.mother, p.father):
            if par:
                kids_of.setdefault(par, []).append(p.id)

    def first_degree(p: Person):
        rel = [x for x in (p.mother, p.father) if x]
        rel += kids_of.get(p.id, [])
        if p.mother and p.father:
            rel += [s for s in kids_of.get(p.mother, []) if s != p.id and by_id[s].father == p.father]
        return rel

    DATA.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    rows, truth, labs = [], [], []
    for p in people:
        c = clinical[p.id]
        # What the chart records about family history: true facts, documented only sometimes.
        rel = first_degree(p)
        rel_cad = any(clinical[r]["cad_age"] is not None and clinical[r]["cad_age"] < PREMATURE_AGE[by_id[r].sex] for r in rel)
        rel_ldl = any(clinical[r]["true_ldl"] >= (LDL_P95_ADULT if age_on(by_id[r], REF_DATE) >= 18 else LDL_P95_CHILD) for r in rel)
        rec_cad = int(rel_cad and rng.random() < 0.35)
        rec_ldl = int(rel_ldl and rng.random() < 0.15)
        rows.append((p.id, f"HL-{p.id:06d}", p.given, p.family, p.sex, p.birth.isoformat(),
                     p.death.isoformat() if p.death else None, p.group, p.household, p.clan, p.mother, p.father,
                     p.lang, p.relatives_abroad,
                     c["statin_start"].isoformat() if c["statin_start"] else None, c["statin_intensity"],
                     round(c["cad_age"], 1) if c["cad_age"] else None, c["xanthoma"], c["arcus"], rec_cad, rec_ldl))
        truth.append((p.id, len(p.alleles), p.alleles[0] if p.alleles else None, round(c["true_ldl"], 2)))
        labs += build_labs(p, c)

    con.executemany(f"INSERT INTO people VALUES ({','.join('?' * 21)})", rows)
    con.executemany("INSERT INTO truth VALUES (?,?,?,?)", truth)
    con.executemany("INSERT INTO spouses VALUES (?,?)", spouses)
    con.executemany("INSERT INTO labs (person_id, date, ldl, tc, hdl, tg, on_statin) VALUES (?,?,?,?,?,?,?)", labs)
    con.commit()

    n_fh = sum(1 for t in truth if t[1] > 0)
    print(f"{len(people)} people, {len(labs)} lipid panels, {n_fh} with FH (1 in {len(people) // max(n_fh, 1)}), "
          f"{sum(1 for t in truth if t[1] > 1)} homozygous")
    con.close()


if __name__ == "__main__":
    main()
