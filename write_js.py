# Write clean JavaScript to external file
js_content = r"""
// Price Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');

    // Count-up animation
    document.querySelectorAll('.stat-value[data-count]').forEach(function(el) {
        var target = parseInt(el.getAttribute('data-count'));
        var duration = 1000;
        var startTime = null;
        function animate(currentTime) {
            if (!startTime) startTime = currentTime;
            var elapsed = currentTime - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * eased);
            if (progress < 1) { requestAnimationFrame(animate); }
            else { el.textContent = target; }
        }
        requestAnimationFrame(animate);
    });

    // Task Status Chart
    function initChart() {
        console.log('initChart called');
        if (typeof Chart === 'undefined') return;
        var canvas = document.getElementById('taskStatusChart');
        var overlay = document.getElementById('chartOverlay');
        if (!canvas || !overlay) return;
        try {
            var tasksByColumn = {{ tasks_by_column|tojson }};
            if (!tasksByColumn || tasksByColumn.length === 0) return;
            var labels = tasksByColumn.map(function(t) { return t.name; });
            var data = tasksByColumn.map(function(t) { return t.count; });
            var colors = ['#818cf8', '#fbbf24', '#4ade80', '#f87171', '#c084fc', '#fb923c'];
            overlay.style.display = 'block';
            new Chart(canvas, {
                type: 'doughnut',
                data: { labels: labels, datasets: [{ data: data, backgroundColor: colors.slice(0, labels.length), borderColor: '#1e293b', borderWidth: 2, hoverOffset: 8 }] },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: '65%',
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#cbd5e1', padding: 12, font: { size: 11 }, usePointStyle: true, pointStyleWidth: 8 } },
                        tooltip: { backgroundColor: '#1e293b', titleColor: '#ffffff', bodyColor: '#cbd5e1', borderColor: '#475569', borderWidth: 1, padding: 10, cornerRadius: 8 }
                    }
                }
            });
        } catch (e) { console.error('Chart error:', e); }
    }

    // Price Dashboard
    function initPriceDashboard() {
        console.log('initPriceDashboard called');
        if (typeof Chart === 'undefined') { console.log('Chart not loaded'); return; }

        var allItems = {{ all_items|tojson }};
        console.log('allItems:', allItems);

        if (!allItems || allItems.length === 0) {
            console.log('No items');
            document.getElementById('noResults').style.display = 'block';
            return;
        }

        var histogramCanvas = document.getElementById('priceHistogram');
        var scatterCanvas = document.getElementById('priceScatter');
        var searchInput = document.getElementById('priceSearch');
        var minPriceInput = document.getElementById('minPrice');
        var maxPriceInput = document.getElementById('maxPrice');
        var resetBtn = document.getElementById('resetFilters');
        var tableBody = document.getElementById('priceTableBody');
        var noResults = document.getElementById('noResults');

        console.log('Elements:', !!histogramCanvas, !!scatterCanvas, !!tableBody);

        var sortField = 'name';
        var sortAsc = true;
        var histogramChart = null;
        var scatterChart = null;

        // Set max price
        var prices = allItems.map(function(i) { return i.price; }).filter(function(p) { return p > 0; });
        if (prices.length > 0) {
            maxPriceInput.setAttribute('placeholder', Math.max.apply(null, prices).toFixed(0));
        }

        function filterItems() {
            var search = (searchInput.value || '').toLowerCase();
            var min = parseFloat(minPriceInput.value) || 0;
            var max = parseFloat(maxPriceInput.value) || Infinity;
            return allItems.filter(function(item) {
                var matchSearch = !search || item.name.toLowerCase().indexOf(search) !== -1;
                var matchMin = item.price >= min;
                var matchMax = max === Infinity || item.price <= max;
                return matchSearch && matchMin && matchMax;
            });
        }

        function sortItems(items) {
            return items.sort(function(a, b) {
                var valA, valB;
                if (sortField === 'name') { valA = a.name.toLowerCase(); valB = b.name.toLowerCase(); }
                else if (sortField === 'price') { valA = a.price; valB = b.price; }
                else if (sortField === 'quantity') { valA = a.quantity; valB = b.quantity; }
                else if (sortField === 'value') { valA = a.price * a.quantity; valB = b.price * b.quantity; }
                if (valA < valB) return sortAsc ? -1 : 1;
                if (valA > valB) return sortAsc ? 1 : -1;
                return 0;
            });
        }

        function updateTable(items) {
            console.log('updateTable:', items.length);
            tableBody.innerHTML = '';
            if (items.length === 0) { noResults.style.display = 'block'; return; }
            noResults.style.display = 'none';
            items.forEach(function(item) {
                var totalValue = (item.price * item.quantity).toFixed(2);
                var tr = document.createElement('tr');
                tr.innerHTML = '<td>' + item.name + '</td><td>$' + item.price.toFixed(2) + '</td><td>' + item.quantity + '</td><td>$' + totalValue + '</td>';
                tableBody.appendChild(tr);
            });
        }

        function updateHistogram(items) {
            console.log('updateHistogram called');
            var bins = [0, 10, 50, 100, 500, Infinity];
            var labels = ['Under $10', '$10-$50', '$50-$100', '$100-$500', '$500+'];
            var counts = [0, 0, 0, 0, 0];
            items.forEach(function(item) {
                for (var i = 0; i < bins.length - 1; i++) {
                    if (item.price >= bins[i] && item.price < bins[i + 1]) { counts[i]++; break; }
                }
            });
            if (histogramChart) histogramChart.destroy();
            histogramChart = new Chart(histogramCanvas, {
                type: 'bar',
                data: { labels: labels, datasets: [{ data: counts, backgroundColor: '#818cf8', borderRadius: 4, borderSkipped: false }] },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false }, title: { display: true, text: 'Price Distribution', color: '#cbd5e1' } }
                }
            });
        }

        function updateScatter(items) {
            console.log('updateScatter called');
            if (scatterChart) scatterChart.destroy();
            scatterChart = new Chart(scatterCanvas, {
                type: 'scatter',
                data: { datasets: [{ data: items.map(function(item) { return { x: item.price, y: item.quantity, name: item.name }; }), backgroundColor: '#818cf8', pointRadius: 5, pointHoverRadius: 7 }] },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false }, title: { display: true, text: 'Price vs Quantity', color: '#cbd5e1' } }
                }
            });
        }

        function refresh() {
            console.log('refresh called');
            var filtered = filterItems();
            var sorted = sortItems(filtered);
            updateTable(sorted);
            updateHistogram(filtered);
            updateScatter(filtered);
        }

        searchInput.addEventListener('input', refresh);
        minPriceInput.addEventListener('input', refresh);
        maxPriceInput.addEventListener('input', refresh);
        resetBtn.addEventListener('click', function() { searchInput.value = ''; minPriceInput.value = ''; maxPriceInput.value = ''; refresh(); });
        document.querySelectorAll('.sortable').forEach(function(th) {
            th.addEventListener('click', function() {
                var field = th.getAttribute('data-sort');
                if (sortField === field) { sortAsc = !sortAsc; }
                else { sortField = field; sortAsc = true; }
                document.querySelectorAll('.sort-icon').forEach(function(icon) { icon.textContent = '↕'; });
                th.querySelector('.sort-icon').textContent = sortAsc ? '↑' : '↓';
                refresh();
            });
        });
        refresh();
        console.log('Price dashboard initialized');
    }

    // Initialize
    if (typeof Chart !== 'undefined') { initChart(); initPriceDashboard(); }
    else {
        var script = document.querySelector('script[src*="chart.js"]');
        if (script) { script.onload = function() { initChart(); initPriceDashboard(); }; }
    }
});
"""

with open('C:/Users/levon_as/Desktop/Tir/static/price_dashboard.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print('JavaScript written to static/price_dashboard.js')
