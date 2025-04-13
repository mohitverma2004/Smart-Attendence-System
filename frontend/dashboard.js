document.addEventListener('DOMContentLoaded', function() {
    // Attendance Chart
    var ctx = document.getElementById('attendanceChart').getContext('2d');
    var attendanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            datasets: [{
                label: 'Attendance Rate (%)',
                data: [85, 87, 84, 90, 82, 75, 78],
                backgroundColor: 'rgba(78, 115, 223, 0.05)',
                borderColor: 'rgba(78, 115, 223, 1)',
                pointBackgroundColor: 'rgba(78, 115, 223, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(78, 115, 223, 1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "rgb(255, 255, 255)",
                    bodyColor: "#858796",
                    titleMarginBottom: 10,
                    titleColor: '#6e707e',
                    titleFontSize: 14,
                    borderColor: '#dddfeb',
                    borderWidth: 1,
                    caretPadding: 10,
                    displayColors: false
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 50,
                    max: 100,
                    ticks: {
                        stepSize: 10
                    },
                    grid: {
                        color: "rgba(0, 0, 0, 0.05)"
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });

    // Real-time clock update
    function updateClock() {
        const now = new Date();
        const dateTimeString = now.toLocaleString('en-US', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        document.getElementById('current-time').textContent = dateTimeString;
    }

    // Add clock element if it exists
    if (document.getElementById('current-time')) {
        updateClock();
        setInterval(updateClock, 1000);
    }

    // Add event listeners for nav items
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Get section id from href
            const sectionId = this.getAttribute('href').substring(1);
            
            // Update the page title
            document.querySelector('main h1').textContent = this.textContent.trim();
            
            // In a real app, load the appropriate content here
            console.log('Loading section: ' + sectionId);
        });
    });

    // Simulate real-time data updates
    function simulateRealTimeUpdates() {
        // Randomly update one of the dashboard metrics
        const metrics = [
            { selector: '.card:nth-child(1) .h5', format: (val) => Math.floor(Math.random() * 8 + 42) + '/50' },
            { selector: '.card:nth-child(2) .h5', format: (val) => Math.floor(Math.random() * 5 + 82) + '%' }
        ];
        
        const randomMetric = metrics[Math.floor(Math.random() * metrics.length)];
        const element = document.querySelector(randomMetric.selector);
        
        if (element) {
            element.textContent = randomMetric.format(element.textContent);
        }
        
        // Add a new activity feed item
        const activities = [
            'User logged in',
            'Attendance recorded for John Doe',
            'New device connected',
            'Attendance report generated',
            'Face recognition successful'
        ];
        
        const activityFeed = document.querySelector('.activity-feed');
        if (activityFeed) {
            const newItem = document.createElement('div');
            newItem.className = 'feed-item';
            
            const dateDiv = document.createElement('div');
            dateDiv.className = 'date';
            dateDiv.textContent = 'Just now';
            
            const textDiv = document.createElement('div');
            textDiv.className = 'text';
            textDiv.textContent = activities[Math.floor(Math.random() * activities.length)];
            
            newItem.appendChild(dateDiv);
            newItem.appendChild(textDiv);
            
            activityFeed.insertBefore(newItem, activityFeed.firstChild);
            
            // Remove the last item if there are more than 5
            if (activityFeed.children.length > 5) {
                activityFeed.removeChild(activityFeed.lastChild);
            }
            
            // Update the other items' timestamps
            const otherItems = activityFeed.querySelectorAll('.feed-item:not(:first-child) .date');
            const times = ['2 mins ago', '15 mins ago', '35 mins ago', '1 hour ago'];
            
            otherItems.forEach((item, index) => {
                if (index < times.length) {
                    item.textContent = times[index];
                }
            });
        }
    }
    
    // Simulate data updates every 30 seconds
    setInterval(simulateRealTimeUpdates, 30000);
});
