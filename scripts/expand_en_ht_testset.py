#!/usr/bin/env python3
"""Merge starter EN↔HT benchmark items into a 200+ sentence extended test set.

All new Haitian Creole strings are best-effort and marked unverified — native
review is required before trusting scores (see benchmarks/README.md).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STARTER = REPO / "benchmarks" / "testset_en_ht.json"
OUT = REPO / "benchmarks" / "testset_en_ht_extended.json"

# Additional pairs: (domain, direction, source, reference)
EXTRA_ITEMS = [
    # everyday
    ("everyday", "en-ht", "I need to leave early today.", "Mwen bezwen ale bonè jodi a."),
    ("everyday", "en-ht", "Can I borrow your phone?", "Èske mwen ka prete telefòn ou?"),
    ("everyday", "en-ht", "The weather is nice today.", "Tan an bèl jodi a."),
    ("everyday", "en-ht", "I will call you later.", "M ap rele ou pita."),
    ("everyday", "en-ht", "Do you have any questions?", "Èske ou gen kesyon?"),
    ("everyday", "en-ht", "I am tired and want to rest.", "Mwen fatige e mwen vle repoze."),
    ("everyday", "en-ht", "My family lives in Port-au-Prince.", "Fanmi mwen rete Pòtoprens."),
    ("everyday", "en-ht", "I work at a hospital.", "Mwen travay nan yon lopital."),
    ("everyday", "en-ht", "She is my sister.", "Li se sè mwen."),
    ("everyday", "en-ht", "We are friends.", "Nou se zanmi."),
    ("everyday", "en-ht", "I like Haitian music.", "Mwen renmen mizik ayisyen."),
    ("everyday", "en-ht", "The food was delicious.", "Manje a te bon."),
    ("everyday", "en-ht", "I am learning Haitian Creole.", "Mwen ap aprann kreyòl ayisyen."),
    ("everyday", "en-ht", "Please repeat that.", "Tanpri repete sa."),
    ("everyday", "en-ht", "I agree with you.", "Mwen dakò avèk ou."),
    ("everyday", "en-ht", "That is not correct.", "Sa pa kòrèk."),
    ("everyday", "en-ht", "I am sorry for the delay.", "Mwen regrèt pou reta a."),
    ("everyday", "en-ht", "Let us meet at noon.", "Ann rankontre midi."),
    ("everyday", "en-ht", "I forgot my keys.", "Mwen bliye kle mwen."),
    ("everyday", "en-ht", "The meeting starts at nine.", "Reyinyon an kòmanse a nèfè."),
    # travel
    ("travel", "en-ht", "I need a taxi to the airport.", "Mwen bezwen yon taksi pou ale nan ayewopò a."),
    ("travel", "en-ht", "Is this seat taken?", "Èske chèz sa a okipe?"),
    ("travel", "en-ht", "The flight is delayed.", "Vòl la an reta."),
    ("travel", "en-ht", "I lost my passport.", "Mwen pèdi paspò mwen."),
    ("travel", "en-ht", "Where can I exchange money?", "Kote mwen ka chanje lajan?"),
    ("travel", "en-ht", "I need a room for two nights.", "Mwen bezwen yon chanm pou de nuit."),
    ("travel", "en-ht", "Is breakfast included?", "Èske dejene enkli?"),
    ("travel", "en-ht", "The bus stop is over there.", "Estasyon bis la la ba."),
    ("travel", "en-ht", "How far is the beach?", "Ki distans lanmè a?"),
    ("travel", "en-ht", "I would like a map of the city.", "Mwen ta renmen yon kat vil la."),
    ("travel", "en-ht", "Please stop here.", "Tanpri kanpe isit."),
    ("travel", "en-ht", "The road is closed.", "Wout la fèmen."),
    ("travel", "en-ht", "I need directions to the hotel.", "Mwen bezwen direksyon pou otèl la."),
    ("travel", "en-ht", "My luggage is missing.", "Baga mwen yo disparèt."),
    ("travel", "en-ht", "Is there Wi-Fi here?", "Èske gen Wi-Fi isit?"),
    # medical
    ("medical", "en-ht", "I feel dizzy.", "Mwen santi mwen vire tèt."),
    ("medical", "en-ht", "I have chest pain.", "Mwen gen doulè nan pwatrin."),
    ("medical", "en-ht", "I cannot breathe well.", "Mwen pa ka respire byen."),
    ("medical", "en-ht", "I need to see a nurse.", "Mwen bezwen wè yon enfimyè."),
    ("medical", "en-ht", "When did the pain start?", "Ki lè doulè a te kòmanse?"),
    ("medical", "en-ht", "I am pregnant.", "Mwen ansent."),
    ("medical", "en-ht", "I have diabetes.", "Mwen gen dyabèt."),
    ("medical", "en-ht", "Take one pill before bed.", "Pran yon grenn avan ou kouche."),
    ("medical", "en-ht", "The wound is bleeding.", "Blesi a ap senyen."),
    ("medical", "en-ht", "I need a wheelchair.", "Mwen bezwen yon chèz woulant."),
    ("medical", "en-ht", "My blood pressure is high.", "Tansyon mwen wo."),
    ("medical", "en-ht", "I fell and hurt my leg.", "Mwen tonbe e mwen blese janm mwen."),
    ("medical", "en-ht", "Do you have insurance?", "Èske ou gen asirans?"),
    ("medical", "en-ht", "The doctor will see you soon.", "Doktè a ap wè ou byento."),
    ("medical", "en-ht", "I need a prescription refill.", "Mwen bezwen ranpli preskripsyon mwen."),
    # emergency
    ("emergency", "en-ht", "There is a fire.", "Gen yon dife."),
    ("emergency", "en-ht", "Someone is hurt.", "Yon moun blese."),
    ("emergency", "en-ht", "Call the police.", "Rele lapolis."),
    ("emergency", "en-ht", "We need an ambulance.", "Nou bezwen yon anbilans."),
    ("emergency", "en-ht", "Stay away from the building.", "Rete lwen bilding la."),
    ("emergency", "en-ht", "Is everyone safe?", "Èske tout moun an sekirite?"),
    ("emergency", "en-ht", "There was an accident on the road.", "Te gen yon aksidan sou wout la."),
    ("emergency", "en-ht", "I smell gas.", "Mwen santi gaz."),
    ("emergency", "en-ht", "Evacuate the area now.", "Evakye zòn nan kounye a."),
    ("emergency", "en-ht", "The child is missing.", "Timoun nan disparèt."),
    # numbers
    ("numbers", "en-ht", "I need two tickets.", "Mwen bezwen de tikè."),
    ("numbers", "en-ht", "The appointment is at three thirty.", "Randevou a se a twaè demi."),
    ("numbers", "en-ht", "It weighs five kilograms.", "Li peze senk kilo."),
    ("numbers", "en-ht", "Room number twelve.", "Chanm nimewo douz."),
    ("numbers", "en-ht", "I am twenty-five years old.", "Mwen gen vennsenk an."),
    ("numbers", "en-ht", "The total is one hundred dollars.", "Total la se san dola."),
    ("numbers", "en-ht", "Call me at this number.", "Rele m nan nimewo sa a."),
    ("numbers", "en-ht", "We need four chairs.", "Nou bezwen kat chèz."),
    ("numbers", "en-ht", "The store opens at eight.", "Magazen an ouvri a witè."),
    ("numbers", "en-ht", "I will return in one hour.", "M ap retounen nan yon èdtan."),
    # idiom / colloquial
    ("idiom", "en-ht", "It is raining cats and dogs.", "Li ap pliye anpil."),
    ("idiom", "en-ht", "Do not worry about it.", "Pa enkyete w pou sa."),
    ("idiom", "en-ht", "That is a great idea.", "Sa se yon bon lide."),
    ("idiom", "en-ht", "I am running late.", "Mwen an reta."),
    ("idiom", "en-ht", "Let us get started.", "Ann kòmanse."),
    ("idiom", "en-ht", "That makes sense.", "Sa gen sans."),
    ("idiom", "en-ht", "I am not sure yet.", "Mwen poko sèten."),
    ("idiom", "en-ht", "Take your time.", "Pran tan ou."),
    ("idiom", "en-ht", "It is up to you.", "Se ou ki deside."),
    ("idiom", "en-ht", "We are almost there.", "Nou prèske rive."),
    # ht-en reverse
    ("everyday", "ht-en", "Mwen bezwen dlo.", "I need water."),
    ("everyday", "ht-en", "Kote mwen ka achte manje?", "Where can I buy food?"),
    ("everyday", "ht-en", "Mwen pa ka jwenn travay la.", "I cannot find the job."),
    ("everyday", "ht-en", "Li ap vini demen.", "He is coming tomorrow."),
    ("everyday", "ht-en", "Nou bezwen pale ansanm.", "We need to talk together."),
    ("travel", "ht-en", "Èske vòl la an reta?", "Is the flight delayed?"),
    ("travel", "ht-en", "Mwen bezwen yon tikè pou Cap-Haïtien.", "I need a ticket to Cap-Haïtien."),
    ("travel", "ht-en", "Ki lè bis la ap pati?", "What time does the bus leave?"),
    ("travel", "ht-en", "Mwen pèdi kat kredi mwen.", "I lost my credit card."),
    ("travel", "ht-en", "Èske otèl la gen chanm vid?", "Does the hotel have empty rooms?"),
    ("medical", "ht-en", "Mwen santi mwen malad.", "I feel sick."),
    ("medical", "ht-en", "Mwen gen doulè nan vant mwen.", "I have pain in my stomach."),
    ("medical", "ht-en", "Doktè a di mwen dwe repoze.", "The doctor told me I must rest."),
    ("medical", "ht-en", "Mwen bezwen yon randevou.", "I need an appointment."),
    ("medical", "ht-en", "Èske medikaman sa a gen efè segondè?", "Does this medicine have side effects?"),
    ("emergency", "ht-en", "Rele lapolis imedyatman.", "Call the police immediately."),
    ("emergency", "ht-en", "Gen yon moun ki bezwen èd.", "There is someone who needs help."),
    ("emergency", "ht-en", "Pa apwoche dife a.", "Do not approach the fire."),
    ("numbers", "ht-en", "Mwen gen senk dola.", "I have five dollars."),
    ("numbers", "ht-en", "Li gen kat pitit.", "She has four children."),
    ("idiom", "ht-en", "Pa fè m mal.", "Do not hurt me."),
    ("idiom", "ht-en", "Sa se pa pwoblèm mwen.", "That is not my problem."),
    ("idiom", "ht-en", "Mwen kontan wè ou.", "I am happy to see you."),
    ("idiom", "ht-en", "Ann ale.", "Let us go."),
    ("idiom", "ht-en", "Mwen pa konnen.", "I do not know."),
    # batch 2 — reach 200+ total
    ("everyday", "en-ht", "I will be right back.", "M ap tounen touswit."),
    ("everyday", "en-ht", "Can you write that down?", "Èske ou ka ekri sa?"),
    ("everyday", "en-ht", "I do not speak Creole well.", "Mwen pa pale kreyòl byen."),
    ("everyday", "en-ht", "My phone battery is dead.", "Batri telefòn mwen fini."),
    ("everyday", "en-ht", "We arrived safely.", "Nou rive an sekirite."),
    ("everyday", "en-ht", "The children are at school.", "Timoun yo lekòl."),
    ("everyday", "en-ht", "I need to buy water.", "Mwen bezwen achte dlo."),
    ("everyday", "en-ht", "It is very hot today.", "Li cho anpil jodi a."),
    ("everyday", "en-ht", "Open the window please.", "Tanpri ouvri fenèt la."),
    ("everyday", "en-ht", "I am looking for my friend.", "M ap chache zanmi mwen."),
    ("travel", "en-ht", "The train leaves in ten minutes.", "Tren nan ap pati nan dis minit."),
    ("travel", "en-ht", "I have a reservation.", "Mwen gen yon rezèvasyon."),
    ("travel", "en-ht", "Is this the right platform?", "Èske se platfòm ki bon an?"),
    ("travel", "en-ht", "I need a receipt.", "Mwen bezwen yon resi."),
    ("travel", "en-ht", "The museum is closed on Monday.", "Mize a fèmen lendi."),
    ("medical", "en-ht", "I have a sore throat.", "Mwen gen mal nan gòj mwen."),
    ("medical", "en-ht", "I need glasses.", "Mwen bezwen linèt."),
    ("medical", "en-ht", "The nurse will check your temperature.", "Enfimyè a ap pran tanperati ou."),
    ("medical", "en-ht", "Do not eat before the test.", "Pa manje anvan tès la."),
    ("medical", "en-ht", "I am allergic to peanuts.", "Mwen fè alèji ak pistach."),
    ("emergency", "en-ht", "There is flooding on the road.", "Gen inondasyon sou wout la."),
    ("emergency", "en-ht", "Power is out in the building.", "Kouran an koupe nan bilding la."),
    ("emergency", "en-ht", "A tree fell on the car.", "Yon pye bwa tonbe sou machin nan."),
    ("numbers", "en-ht", "The meeting is on the fifteenth.", "Reyinyon an se kenzyèm."),
    ("numbers", "en-ht", "I need change for twenty dollars.", "Mwen bezwen monnen pou ven dola."),
    ("idiom", "en-ht", "Better late than never.", "Pi bon an reta pase pa janm."),
    ("everyday", "ht-en", "Mwen vle ale nan mache a.", "I want to go to the market."),
    ("everyday", "ht-en", "Tan an ap pliye.", "It is raining."),
    ("everyday", "ht-en", "Mwen pa gen lajan.", "I do not have money."),
    ("everyday", "ht-en", "Ki lè ou ap vini?", "What time are you coming?"),
    ("travel", "ht-en", "Machin nan pa mache.", "The car is not working."),
    ("travel", "ht-en", "Mwen bezwen yon kat pou vil la.", "I need a map of the city."),
    ("medical", "ht-en", "Mwen gen kase.", "I have a cough."),
    ("medical", "ht-en", "Mwen pa ka dòmi.", "I cannot sleep."),
    ("emergency", "ht-en", "Tanpri rele yon anbilans.", "Please call an ambulance."),
    ("numbers", "ht-en", "Li gen swasant an.", "He is sixty years old."),
    ("idiom", "ht-en", "Sa pa enpòtan.", "That does not matter."),
    ("idiom", "ht-en", "Mwen swete ou bon chans.", "I wish you good luck."),
    ("everyday", "en-ht", "I enjoyed talking with you.", "Mwen te kontan pale avèk ou."),
    ("everyday", "ht-en", "Mwen pa tande byen.", "I did not hear well."),
]


def main() -> None:
    starter = json.loads(STARTER.read_text(encoding="utf-8"))
    items = list(starter["items"])
    existing_ids = {it["id"] for it in items}
    prefix_map = {
        "everyday": "ex",
        "travel": "xt",
        "medical": "xm",
        "emergency": "xg",
        "numbers": "xn",
        "idiom": "xi",
    }
    counters = {k: 1 for k in prefix_map}

    for domain, direction, source, reference in EXTRA_ITEMS:
        prefix = prefix_map[domain]
        while True:
            item_id = f"{prefix}{counters[domain]:02d}"
            counters[domain] += 1
            if item_id not in existing_ids:
                break
        existing_ids.add(item_id)
        items.append({
            "id": item_id,
            "domain": domain,
            "direction": direction,
            "source": source,
            "reference": reference,
            "review_status": "unverified",
            "notes": "Extended set — requires native HT review.",
        })

    out = {
        "meta": {
            **starter["meta"],
            "name": "Anai Translator EN<->HT extended set (200+)",
            "version": "0.2.0",
            "item_count": len(items),
            "review_status": "UNVERIFIED",
            "review_note": (
                f"{len(items)} items. All Haitian Creole strings remain best-effort "
                "until a fluent speaker sets review_status to verified."
            ),
        },
        "items": items,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
