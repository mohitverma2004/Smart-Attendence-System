// Main application script
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the application
    initApp();
    
    // Setup authentication
    setupAuth();
    
    // Setup navigation
    setupNavigation();
});

function initApp() {
    console.log('Smart Attendance System initialized at', new Date().toLocaleString());
    
    // Check if user is logged in
    checkAuthStatus();
    
    // Load initial data
    loadDashboardData();
}

function checkAuthStatus() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        // Redirect to login page in a real application
        console.log('User not authenticated');
    } else {
        console.log('User authenticated');
        // Fetch user data in a real application
    }
}

function loadDashboardData() {
    // In a real application, this would make API calls to fetch dashboard data
    console.log('Loading dashboard data...');
    
    // Simulate API fetch delay
    setTimeout(() => {
        console.log('Dashboard data loaded');
        // Here you would update the UI with the fetched data
    }, 1000);
}

function setupAuth() {
    // Setup login/logout functionality
    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'login-btn') {
            login();
        } else if (e.target && e.target.id === 'logout-btn') {
            logout();
        }
    });
}

function login() {
    // In a real app, this would validate credentials and make an API call
    console.log('Logging in...');
    localStorage.setItem('authToken', 'sample-token-' + Date.now());
    checkAuthStatus();
}

function logout() {
    console.log('Logging out...');
    localStorage.removeItem('authToken');
    checkAuthStatus();
}

function setupNavigation() {
    // Setup navigation events
    const contentSection = document.getElementById('dashboard-content');
    
    // Handle navigation clicks
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('nav-link')) {
            e.preventDefault();
            const targetId = e.target.getAttribute('href').substring(1);
            navigateTo(targetId);
        }
    });
}

function navigateTo(sectionId) {
    console.log('Navigating to', sectionId);
    
    // In a real SPA, this would load the appropriate content
    // For this demo, we'll just log the navigation
    
    // Update active navigation item
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === '#' + sectionId) {
            link.classList.add('active');
        }
    });
}

// Real-time notifications handler
function setupNotifications() {
    // In a real app, this would connect to a WebSocket for real-time updates
    console.log('Setting up real-time notifications');
    
    // Simulate incoming notifications
    setInterval(() => {
        const events = [
            'New user registered',
            'Attendance marked for John Doe',
            'System alert: Camera 2 offline',
            'Daily report generated',
            'Unauthorized access attempt detected'
        ];
        
        const randomEvent = events[Math.floor(Math.random() * events.length)];
        showNotification(randomEvent);
    }, 45000); // Every 45 seconds
}

function showNotification(message) {
    console.log('Notification:', message);
    
    // In a real app, this would display a toast or notification badge
    // For this demo, we'll just log to console
}

// Initialize notifications
setupNotifications();
