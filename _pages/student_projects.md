---
layout: archive
title: "Studentische Projekte"
permalink: /student_projects/
author_profile: true
---

{% include base_path %}
{% include toc %}

{% assign typed_projects = site.student_projects | where_exp: "item", "item.type != nil" %}
{% assign other_projects = site.student_projects | where_exp: "item", "item.type == nil" %}

{% for post in other_projects %}
  {% include archive-single.html hide_details=true %}
{% endfor %}

## Bewertungskriterien für studentische Arbeiten

Die Bewertung von Projekt- und Abschlussarbeiten erfolgt anhand der folgenden Kriterien. Diese dienen als Orientierungshilfe für eine erfolgreiche Bearbeitung und machen die Benotung transparent.

| Kriterium | Beschreibung |
| :--- | :--- |
| **Problemdefinition & Zielsetzung** | Klare Formulierung und Abgrenzung des Problems, Zielstellung der Arbeit, Forschungsfrage(n) |
| **Fachliche Tiefe & Informatikbezug** | Anwendung informatischer Konzepte, Theorien, Algorithmen, Architektur, Modellierung etc. |
| **Methodik & Vorgehen** | Auswahl und Begründung von Methoden, z. B. agile Entwicklung, Modellierung, Experimente, Evaluation |
| **Technische Umsetzung & Ergebnisse** | Qualität der Implementierung, Systemarchitektur, Softwarequalität, Datenanalyse etc. |
| **Kritische Reflexion & Bewertung** | Eigene Ergebnisse werden hinterfragt, Limitationen erkannt, alternative Ansätze diskutiert |
| **Wissenschaftliches Arbeiten & Literatur** | Umgang mit Quellen, Zitierweise, wissenschaftlicher Stil, Qualität der Literaturrecherche |
| **Struktur, Sprache & Verständlichkeit** | Aufbau der Arbeit, Lesbarkeit, Klarheit der Darstellung, Fachsprache |
| **Selbstständigkeit & Originalität** | Eigenanteil, kreative Ansätze, Initiative bei der Umsetzung |

## Abgeschlossene Arbeiten

{% assign projects_by_type = typed_projects | group_by: 'type' %}

{% comment %} Define the order of types {% endcomment %}
{% assign type_order = "Bachelorthesis,Masterthesis,Praxisprojekt" | split: "," %}

{% for type_name in type_order %}
{% assign type_group = projects_by_type | where: "name", type_name | first %}
{% if type_group %}
### {{ type_name }}
{: #{{ type_name | slugify }} }

{% assign sorted_items = type_group.items | sort: 'date' | reverse %}
{% assign current_semester = "" %}

{% for post in sorted_items %}
{% if post.semester != current_semester %}
#### {{ post.semester }}
{: #{{ type_name | slugify }}-{{ post.semester | slugify }} }
{% assign current_semester = post.semester %}
{% endif %}
{% include archive-single.html hide_details=true %}
{% endfor %}
{% endif %}
{% endfor %}
