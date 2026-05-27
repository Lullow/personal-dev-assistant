# Personal Dev Assistant

Personal Dev Assistant är ett planerat AI-agentprojekt för en förenklad terminalbaserad coding assistant. Tanken är att bygga en liten skolversion av verktyg som Claude Code eller Codex CLI, men med tydlig och hanterbar omfattning för ett kursprojekt.

Projektet är under utveckling. I den här fasen finns bara repo-struktur, dokumentation, krav och prompt-placeholders. Själva agentimplementationen byggs senare.

## Planerad funktionalitet

- Hjälpa till i ett lokalt kodprojekt via terminalen.
- Läsa filer och sammanfatta relevant information.
- Köra säkra bash-kommandon med skydd mot riskabla kommandon.
- Göra små eller partiella filändringar.
- Avgöra om den ska göra fler tool-calls eller lämna tillbaka ett svar till användaren.
- Använda en main agent som kan starta specialiserade sub-agenter.
- Ha sub-agenter för planering, utforskning, kodändringar och review/safety.
- Sammanfatta långa tool outputs innan de läggs i aktiv context.
- Följa token- och kostnadsbudget med warnings och hard cap.
- Vara enkel att konfigurera och starta, till exempel via Docker eller tydlig setup.

## Demo-idé

Den tänkta demon är att agenten får arbeta i ett litet Python-projekt med ett failing test. Agenten ska undersöka projektet, hitta buggen, föreslå eller göra en liten ändring, köra tester igen och sammanfatta vad som hände.

Ett första litet demo-projekt finns i `demo_project/`. Det innehåller en avsiktligt felaktig calculator-funktion och ett test som används för den planerade demon.
