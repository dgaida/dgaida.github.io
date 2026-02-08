document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('project-search');
  const typeFilter = document.getElementById('type-filter');
  const semesterFilter = document.getElementById('semester-filter');
  const tagFilter = document.getElementById('tag-filter');

  const items = document.querySelectorAll('.list__item, .grid__item');

  function filter() {
    const searchTerm = searchInput.value.toLowerCase();
    const selectedType = typeFilter.value;
    const selectedSemester = semesterFilter.value;
    const selectedTag = tagFilter.value;

    items.forEach(item => {
      const title = item.querySelector('.archive__item-title').textContent.toLowerCase();
      const type = item.dataset.type;
      const semester = item.dataset.semester;
      const tags = JSON.parse(item.dataset.tags || '[]');

      const matchesSearch = title.includes(searchTerm);
      const matchesType = !selectedType || type === selectedType;
      const matchesSemester = !selectedSemester || semester === selectedSemester;
      const matchesTag = !selectedTag || tags.includes(selectedTag);

      if (matchesSearch && matchesType && matchesSemester && matchesTag) {
        item.style.display = 'block';
      } else {
        item.style.display = 'none';
      }
    });

    // Hide/show headers if no items are visible in a section
    // This is a bit complex in Minimal Mistakes as it groups by year/type
    // For now, we just filter the items themselves.
  }

  if (searchInput) searchInput.addEventListener('input', filter);
  if (typeFilter) typeFilter.addEventListener('change', filter);
  if (semesterFilter) semesterFilter.addEventListener('change', filter);
  if (tagFilter) tagFilter.addEventListener('change', filter);
});
