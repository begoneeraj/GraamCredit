/* =============================================
   GraamCredit — lang-config.js
   Global translation, active nav, and mobile menu
   ============================================= */

// State
var currentLang = localStorage.getItem('graamcredit_lang') || 'en';

// Export toggle to global scope for inline onclick triggers
window.toggleLanguage = function() {
  currentLang = currentLang === 'en' ? 'hi' : 'en';
  localStorage.setItem('graamcredit_lang', currentLang);
  applyLanguage();
};

function applyLanguage() {
  // Update page html lang attribute
  document.documentElement.lang = currentLang;

  // 1. Update all language toggle labels/pills
  const langLabels = document.querySelectorAll('#langLabel');
  langLabels.forEach(el => {
    // If it has standard label display like "हिन्दी" (on form page)
    if (el.getAttribute('data-custom-toggle') === 'target') {
      el.textContent = currentLang === 'en' ? 'हिन्दी' : 'English';
    } else {
      // Default navbar pill label "EN | हिंदी"
      el.textContent = currentLang === 'en' ? 'EN | हिंदी' : 'हिंदी | EN';
    }
  });

  // 2. Translate all elements with data-en / data-hi
  document.querySelectorAll('[data-en]').forEach(el => {
    const text = el.getAttribute(`data-${currentLang}`);
    if (text !== null) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = text;
      } else {
        el.textContent = text;
      }
    }
  });

  // 3. Dispatch global event for other scripts to respond (e.g. form, results)
  document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: currentLang } }));
}

function runLangInit() {
  applyLanguage();

  // Active navigation link highlighting
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.navbar-links a, .navbar-mobile-menu a').forEach(a => {
    if ((a.getAttribute('href') || '').split('#')[0] === page) {
      a.classList.add('active');
    } else {
      a.classList.remove('active');
    }
  });

  // Mobile Hamburger menu toggle logic
  const hamburger = document.getElementById('hamburgerBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', (e) => {
      e.stopPropagation();
      mobileMenu.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!document.getElementById('navbar')?.contains(e.target)) {
        mobileMenu.classList.remove('open');
      }
    });
  }
}

if (document.readyState !== 'loading') {
  runLangInit();
} else {
  document.addEventListener('DOMContentLoaded', runLangInit);
}
