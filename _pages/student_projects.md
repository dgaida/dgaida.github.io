---
layout: archive
title: "Studentische Projekte"
permalink: /student_projects/
author_profile: true
header:
  teaser: /assets/images/student_projects_teaser.jpg
---

Auf dieser Seite finden Sie eine Übersicht über abgeschlossene Bachelor- und Masterthesen sowie Praxisprojekte, die von mir betreut wurden.

<style>
/* Timeline Styles */
.timeline {
  position: relative;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 0;
}
.timeline::after {
  content: '';
  position: absolute;
  width: 6px;
  background-color: #f1f1f1;
  top: 0;
  bottom: 0;
  left: 50%;
  margin-left: -3px;
}
.timeline-container {
  padding: 10px 40px;
  position: relative;
  background-color: inherit;
  width: 50%;
}
.timeline-container::after {
  content: '';
  position: absolute;
  width: 25px;
  height: 25px;
  right: -17px;
  background-color: white;
  border: 4px solid #333;
  top: 15px;
  border-radius: 50%;
  z-index: 1;
}
.left { left: 0; }
.right { left: 50%; }
.left::after { left: auto; right: -13px; }
.right::after { left: -12px; }
.timeline-content {
  padding: 20px 30px;
  background-color: white;
  position: relative;
  border-radius: 6px;
  box-shadow: 0 4px 8px 0 rgba(0,0,0,0.1);
  border: 1px solid #eee;
}
@media screen and (max-width: 600px) {
  .timeline::after { left: 31px; }
  .timeline-container { width: 100%; padding-left: 70px; padding-right: 25px; }
  .timeline-container::after { left: 15px; }
  .right { left: 0%; }
}

/* Filter Styles */
.project-filters {
  margin-bottom: 30px;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
}
.filter-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.filter-group select, .filter-group input {
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ccc;
}
.filter-group input { flex-grow: 1; }

/* Stats Styles */
.stats-container {
  display: flex;
  justify-content: space-around;
  background: #f9f9f9;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 30px;
  text-align: center;
}
.stat-item h3 { margin: 0; font-size: 1.2em; }
.stat-item p { margin: 5px 0 0; font-weight: bold; font-size: 1.5em; color: #333; }
</style>

{% assign projects = site.student_projects | sort: 'date' | reverse %}

## Timeline

<div class="timeline">
  {% for project in projects limit:6 %}
    <div class="timeline-container {% cycle 'left', 'right' %}">
      <div class="timeline-content">
        <small>{{ project.date | date: "%B %Y" }}</small>
        <h3 style="margin: 5px 0;">{{ project.title }}</h3>
        <p style="margin: 0;">{{ project.author_initials }} - {{ project.type }}</p>
      </div>
    </div>
  {% endfor %}
</div>

## Statistik

<div class="stats-container">
  <div class="stat-item">
    <h3>Nach Typ:</h3>
    {% assign types = projects | map: 'type' | uniq %}
    {% for type in types %}
      {% if type %}
      <span style="font-size: 0.9em;">{{ type }}: {{ projects | where: "type", type | size }}</span><br>
      {% endif %}
    {% endfor %}
  </div>
  <div class="stat-item">
    <h3>Nach Semester:</h3>
    {% assign semesters = projects | map: 'semester' | uniq %}
    {% for sem in semesters %}
      {% if sem %}
      <span style="font-size: 0.9em;">{{ sem }}: {{ projects | where: "semester", sem | size }}</span><br>
      {% endif %}
    {% endfor %}
  </div>
  <div class="stat-item">
    <h3>Gesamt:</h3>
    <p>{{ projects | size }} Projekte</p>
  </div>
</div>

## Abgeschlossene Arbeiten

<div class="project-filters">
  <input type="text" id="project-search" placeholder="Suche nach Titeln..." style="width: 100%; padding: 10px; margin-bottom: 10px;">
  <div class="filter-group">
    <select id="type-filter">
      <option value="">Alle Typen</option>
      {% assign types = projects | map: 'type' | uniq %}
      {% assign types_sorted = types | compact | sort %}
      {% for type in types_sorted %}<option value="{{ type }}">{{ type }}</option>{% endfor %}
    </select>
    <select id="semester-filter">
      <option value="">Alle Semester</option>
      {% assign semesters = projects | map: 'semester' | uniq %}
      {% assign semesters_sorted = semesters | compact | sort | reverse %}
      {% for sem in semesters_sorted %}<option value="{{ sem }}">{{ sem }}</option>{% endfor %}
    </select>
    <select id="tag-filter">
      <option value="">Alle Themen</option>
      {% assign all_tags = "" | split: "," %}
      {% for project in projects %}
        {% if project.tags %}
          {% for tag in project.tags %}
            {% assign all_tags = all_tags | push: tag %}
          {% endfor %}
        {% endif %}
      {% endfor %}
      {% assign all_tags_sorted = all_tags | uniq | compact | sort %}
      {% for tag in all_tags_sorted %}
        {% if tag != "" %}
          <option value="{{ tag }}">{{ tag }}</option>
        {% endif %}
      {% endfor %}
    </select>
  </div>
</div>

{% for project_type in types %}
  {% if project_type %}
  <h3 id="{{ project_type | slugify }}">{{ project_type }}</h3>
  {% assign type_projects = projects | where: "type", project_type %}
  {% assign semester_groups = type_projects | map: 'semester' | uniq | sort | reverse %}

  {% for sem in semester_groups %}
    {% if sem %}
    <h4 style="color: #666;">{{ sem }}</h4>
    <div class="entries-{{ project_type | slugify }}">
    {% for post in type_projects %}
      {% if post.semester == sem %}
        {% include archive-single.html hide_details=true %}
      {% endif %}
    {% endfor %}
    </div>
    {% endif %}
  {% endfor %}
  {% endif %}
{% endfor %}

<script src="{{ '/assets/js/filter-projects.js' | relative_url }}"></script>
