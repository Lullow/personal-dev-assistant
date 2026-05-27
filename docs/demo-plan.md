# Demo Plan

Den tänkta demon ska visa hur Personal Dev Assistant kan hjälpa till i ett litet lokalt kodprojekt.

## Scenario

Agenten får ett litet Python-projekt med ett failing test. Projektet ska vara enkelt nog att förstå snabbt, men tillräckligt realistiskt för att visa hur agenten arbetar stegvis.

Ett första demo-projekt finns i `demo_project/`. Det här dokumentet beskriver hur det ska användas när agentimplementationen finns på plats.

## Tänkt arbetsflöde

1. Användaren startar agenten i demo-projektets rotmapp.
2. Användaren ber agenten undersöka varför testerna failar.
3. Agenten listar relevanta filer.
4. Agenten läser testfilen och den kod som testas.
5. Agenten kör testerna.
6. Agenten analyserar testfelet.
7. Agenten hittar en liten bugg.
8. Agenten föreslår eller gör en begränsad filändring.
9. Agenten kör testerna igen.
10. Agenten sammanfattar vad den gjorde och vilket resultat det gav.

## Vad demon ska visa

- Att agenten kan arbeta stegvis.
- Att den kan använda tools på ett kontrollerat sätt.
- Att den kan hantera context genom att sammanfatta relevant output.
- Att den kan göra en liten, fokuserad ändring.
- Att den kan verifiera ändringen med tester.
- Att den kan förklara sitt arbete för användaren.

## Begränsningar

- Demon ska vara liten och tydlig.
- Den ska inte kräva internetåtkomst.
- Den ska inte innehålla riskabla kommandon.
- Den ska inte försöka visa allt systemet kan göra på en gång.
