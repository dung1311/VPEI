// ===================================
// SYNEK WEBSITE - MAIN JAVASCRIPT
// ===================================

// Toggle Mobile Menu
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileMenu.classList.contains('hidden')) {
        mobileMenu.classList.remove('hidden');
    } else {
        mobileMenu.classList.add('hidden');
    }
}

// Toggle Search Bar
function toggleSearch() {
    const searchBar = document.getElementById('searchBar');
    if (searchBar.classList.contains('hidden')) {
        searchBar.classList.remove('hidden');
        searchBar.querySelector('input').focus();
    } else {
        searchBar.classList.add('hidden');
    }
}

// Perform Search
function performSearch() {
    const searchInput = document.getElementById('searchBar').querySelector('input');
    const searchTerm = searchInput.value.trim();
    
    if (searchTerm) {
        alert(`Tìm kiếm: "${searchTerm}"\n\nChức năng tìm kiếm sẽ được triển khai sau.`);
    } else {
        alert('Vui lòng nhập từ khóa tìm kiếm');
    }
}

// Change Language
function changeLang(lang) {
    const viBtn = document.getElementById('lang-vi');
    const enBtn = document.getElementById('lang-en');
    
    if (lang === 'vi') {
        viBtn.classList.add('translate-active');
        viBtn.classList.remove('text-gray-500');
        enBtn.classList.remove('translate-active');
        enBtn.classList.add('text-gray-500');
        alert('Ngôn ngữ: Tiếng Việt\n\nChức năng đa ngôn ngữ sẽ được triển khai sau.');
    } else {
        enBtn.classList.add('translate-active');
        enBtn.classList.remove('text-gray-500');
        viBtn.classList.remove('translate-active');
        viBtn.classList.add('text-gray-500');
        alert('Language: English\n\nMulti-language feature coming soon.');
    }
}

// Open Login Modal
function openLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) {
        modal.classList.add('show');
    }
}

// Close Login Modal
function closeLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// Handle Login Form Submit
function handleLoginSubmit(event) {
    event.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    if (email && password) {
        alert(`Đăng nhập với:\nEmail: ${email}\n\nChức năng đăng nhập sẽ được triển khai sau.`);
        closeLoginModal();
    }
}

// Filter News by Category (for tintuc.html)
function filterNews(category) {
    const newsCards = document.querySelectorAll('[data-category]');
    const badges = document.querySelectorAll('.category-badge');
    
    // Update badge styles
    badges.forEach(badge => {
        badge.classList.remove('bg-blue-700', 'text-white');
        badge.classList.add('bg-gray-200', 'text-gray-700');
    });
    event.target.classList.remove('bg-gray-200', 'text-gray-700');
    event.target.classList.add('bg-blue-700', 'text-white');
    
    // Filter news cards
    newsCards.forEach(card => {
        if (category === 'all' || card.getAttribute('data-category') === category) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// Handle Contact Form Submit (for lienhe.html)
function handleContactSubmit(event) {
    event.preventDefault();
    const name = document.getElementById('contactName').value;
    const email = document.getElementById('contactEmail').value;
    const phone = document.getElementById('contactPhone').value;
    const message = document.getElementById('contactMessage').value;
    
    if (name && email && phone && message) {
        alert(`Cảm ơn ${name}!\n\nChúng tôi đã nhận được thông tin của bạn:\n• Email: ${email}\n• Điện thoại: ${phone}\n\nChúng tôi sẽ liên hệ lại trong vòng 24 giờ.`);
        event.target.reset();
    }
}

// Scroll to Section
function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Initialize Page
document.addEventListener('DOMContentLoaded', function() {
    // Close modal when clicking outside
    window.onclick = function(event) {
        const modal = document.getElementById('loginModal');
        if (event.target == modal) {
            closeLoginModal();
        }
    }
    
    // Handle Enter key in search
    const searchInput = document.getElementById('searchBar')?.querySelector('input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        });
    }
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });
    
    console.log('SYNEK Website Initialized');
});

// Stats Counter Animation (for index.html)
function animateCounter(element, target, duration = 2000) {
    let start = 0;
    const increment = target / (duration / 16);
    const timer = setInterval(() => {
        start += increment;
        if (start >= target) {
            element.textContent = target + '+';
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(start) + '+';
        }
    }, 16);
}

// Initialize counters when visible
const observerOptions = {
    threshold: 0.5
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.animated) {
            const target = parseInt(entry.target.dataset.target);
            animateCounter(entry.target, target);
            entry.target.dataset.animated = 'true';
        }
    });
}, observerOptions);

// Observe all counter elements
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-target]').forEach(counter => {
        observer.observe(counter);
    });
});
