# Dokumentation: Berechnung der Prüfungszeiträume (Informatik)

Dieses Verzeichnis enthält die automatisch generierten Vorschläge für die Prüfungszeiträume des Informatikstudiengangs der TH Köln. Die Berechnungen werden durch das Skript `scripts/calculate_exam_periods.py` durchgeführt.

## Datenquellen

Das Skript parst dynamisch die folgenden offiziellen Webseiten der TH Köln:
1. **Vorlesungszeiten**: [Allgemeine Vorlesungszeiten](https://www.th-koeln.de/studium/vorlesungszeiten_357.php)
2. **HIP-Wochen**: [Interdisziplinäre Projektwoche (Terminvorschau)](https://www.th-koeln.de/studium/interdisziplinaere-projektwoche_48320.php)

## Planungslogik

Die Prüfungszeiträume werden pro Semester nach folgendem Schema festgelegt:

### Struktur der Prüfungswochen
- **Sommersemester (SS)**: 3 Prüfungswochen
  - P1: Zu Beginn der Vorlesungszeit (1 Woche)
  - P2: Während der HIP-Woche (1 Woche)
  - P3: Am Ende der Vorlesungszeit (1 Woche)
- **Wintersemester (WS)**: 4 Prüfungswochen
  - P1a & P1b: Zu Beginn der Vorlesungszeit (2 aufeinanderfolgende Wochen)
  - P2: Während der HIP-Woche (1 Woche)
  - P3: Am Ende der Vorlesungszeit (1 Woche)

### Berücksichtigte Randbedingungen (Constraints)
1. **Minimale Vorlesungszeit**: Das Semester muss insgesamt mindestens **13 Vorlesungswochen** umfassen.
2. **Buffer vor HIP**: Zwischen den ersten Prüfungswochen (P1/P1b) und der HIP-Woche (P2) müssen genau **7 reine Vorlesungswochen** liegen.
3. **Buffer nach HIP**: Zwischen der HIP-Woche (P2) und der letzten Prüfungswoche (P3) müssen genau **7 reine Vorlesungswochen** liegen.

### Feiertags- und Sonderregeln
- **"Freitag-vorher"-Regel**: Fällt ein gesetzlicher Feiertag (NRW) in die reguläre Prüfungswoche (Mo-Fr), wird der Prüfungszeitraum um die entsprechende Anzahl Tage auf den/die Freitag(e) der Vorwoche vorgezogen, um volle 5 Prüfungstage zu gewährleisten.
- **Oster-Regel**: In der Woche des Ostermontags finden keine Prüfungen statt. Der Zeitraum wird um eine Woche nach hinten verschoben, sofern die Bedingung von mindestens 13 Vorlesungswochen weiterhin erfüllt bleibt.
- **Weihnachts-/Neujahrspause (nur WS)**: Wochen, in denen der 24.-26.12. oder der 01.01. auf einen Arbeitstag (Mo-Fr) fallen, werden nicht als Vorlesungswochen gezählt.
- **Karneval**: Die Karnevalswoche (Woche mit Weiberfastnacht) wird im Plan explizit markiert. Rosenmontag wird als Feiertag (Köln-spezifisch) berücksichtigt.

## Automatische Anpassung (Optimierung)
Sollten die Standard-Termine (basierend auf dem Vorlesungsbeginn/-ende) die 7-Wochen-Buffer verletzen, verschiebt das Skript:
- Den Beginn (P1) nach vorne, um den Buffer vor der HIP-Woche zu vergrößern.
- Das Ende (P3) nach hinten, um den Buffer nach der HIP-Woche zu vergrößern.

Falls keine Lösung gefunden wird, die alle Bedingungen gleichzeitig erfüllt, werden mehrere Varianten (z. B. "Standard" vs. "Optimierungsversuch") ausgegeben und die jeweils verletzten Bedingungen markiert.

## Dateien
- `exam_periods.md`: Detaillierter Bericht mit Tabellen, Feiertagsangaben und Vorlesungswochen-Statistiken.
- `exam_periods.ics`: Kalenderdatei im iCalendar-Format zum Import in Outlook, Google Calendar etc.
