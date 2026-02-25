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

### Vorschlag vs. Fix
- **Fixe Termine**: Termine, die offiziell auf der TH-Webseite für die Interdisziplinäre Projektwoche (HIP) angekündigt sind, werden prioritär übernommen, auch wenn sie die Buffer-Regeln verletzen.
- **Vorschläge**: Für alle weiteren Semester (ab Sommersemester 2028) berechnet das Skript optimale Zeiträume, die strikt die 7-Wochen-Regel anstreben und Feiertage sowie Semesterferien berücksichtigen.

### Feiertags- und Sonderregeln
- **"Freitag-vorher"-Regel**: Fällt ein gesetzlicher Feiertag (NRW) in die reguläre Prüfungswoche (Mo-Fr), wird der Prüfungszeitraum um die entsprechende Anzahl Tage auf den/die Freitag(e) der Vorwoche vorgezogen, um volle 5 Prüfungstage zu gewährleisten.
  - *Abhängigkeit*: Sollte durch das Vorziehen ein Konflikt mit der vorangegangenen Prüfungswoche entstehen (Überlappung), wird auch die vorangegangene Woche entsprechend auf den/die Freitag(e) ihrer Vorwoche vorgezogen.
- **Zählung der Vorlesungswochen**: Eine Woche gilt nur dann als volle Vorlesungswoche, wenn sie keinen Prüfungstag enthält. Beginnt eine Prüfung beispielsweise an einem Freitag einer regulären Vorlesungswoche, wird diese Woche in der Statistik nicht mehr als Vorlesungswoche gezählt.
- **Oster-Regel**: In der Woche des Ostermontags finden keine Prüfungen statt. Der Zeitraum wird um eine Woche nach hinten verschoben, sofern die Bedingung von mindestens 13 Vorlesungswochen weiterhin erfüllt bleibt.
- **Weihnachts-/Neujahrspause (nur WS)**: Wochen, in denen der 24.-26.12. oder der 01.01. auf einen Arbeitstag (Mo-Fr) fallen, werden nicht als Vorlesungswochen gezählt.
- **Karneval**: Die Karnevalswoche (Woche mit Weiberfastnacht) wird im Plan explizit markiert. Rosenmontag wird als Feiertag (Köln-spezifisch) berücksichtigt.

## Automatische Anpassung (Optimierung)
Sollten die Standard-Termine (basierend auf dem Vorlesungsbeginn/-ende) die 7-Wochen-Buffer verletzen, verschiebt das Skript:
- Den Beginn (P1) nach vorne (maximal eine Woche vor Vorlesungsbeginn), um den Buffer vor der HIP-Woche zu vergrößern.
- Das Ende (P3) nach hinten (maximal eine Woche nach Vorlesungsende), um den Buffer nach der HIP-Woche zu vergrößern.

Dabei gilt die **"No-Gap"-Regel**: Prüfungszeiträume, die außerhalb der offiziellen Vorlesungszeit liegen, müssen unmittelbar an diese angrenzen. Es werden keine "Lückenwochen" zwischen Prüfung und Vorlesung eingeplant. Wenn der 7-Wochen-Buffer auch durch diese Verschiebung nicht erreicht wird, wird der kürzere Buffer akzeptiert und eine Warnung ausgegeben.

Falls keine Lösung gefunden wird, die alle Bedingungen gleichzeitig erfüllt, werden mehrere Varianten (z. B. "Standard" vs. "Optimierungsversuch") ausgegeben und die jeweils verletzten Bedingungen markiert.

## Dateien
- `exam_periods.md`: Detaillierter Bericht mit Tabellen, Feiertagsangaben und Vorlesungswochen-Statistiken.
- `exam_periods.ics`: Kalenderdatei im iCalendar-Format zum Import in Outlook, Google Calendar etc.
