# Aftermovie-tool

Maakt van de registratie van een voorstelling, plus je eigen bouwfilmpjes en foto's, een korte aftermovie (onder de minuut) voor je portfolio. Het gaat om het decor en de effecten, niet om het spel.

## Gebruik

1. Open Claude Code in deze map.
2. Zeg: **maak een aftermovie van ~/Downloads/Silo8** (of een andere projectmap).
3. Claude vraagt welke momenten er zeker in moeten, laat zien wat het vindt, en maakt een eerste versie. Daarna stuur je bij: "langer", "deze eruit", "meer vuur".

Een projectmap bevat de registratie (het grootste videobestand), een map `Film/` met bouwfilmpjes en een map `Foto/` met foto's.

## Goed om te weten

- De video's blijven op je eigen computer. Alleen losse stilstaande beelden gaan naar Claude om te beschrijven.
- Er wordt nooit beeld door AI gemaakt. Alles in de film is echt materiaal.
- De werkbestanden en films komen in `work/` en gaan nooit mee naar GitHub.

Hoe het werkt staat in `.claude/skills/aftermovie/SKILL.md`; de scripts staan in `scripts/`.
