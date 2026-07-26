/* =============================================
   GraamCredit — script.js
   Form logic, validation, scoring, localStorage
   ============================================= */

// ---- State ----
let currentStep = 1;
const totalSteps = 5;
var currentLang = localStorage.getItem('graamcredit_lang') || 'en';

// ---- Step Labels ----
const stepLabels = {
  en: ['Consent', 'Personal Info', 'Financial', 'Digital Activity', 'Review'],
  hi: ['सहमति', 'व्यक्तिगत जानकारी', 'वित्तीय', 'डिजिटल गतिविधि', 'समीक्षा'],
};

// ---- Language Translations ----
const formTranslations = {
  // Step 1
  step1Title: { en: 'Data Consent & Privacy', hi: 'डेटा सहमति और गोपनीयता' },
  step1Desc: { en: 'We collect your financial data with your permission to assess loan eligibility. Your data is protected under Indian data protection laws.', hi: 'हम आपकी अनुमति से ऋण पात्रता का आकलन करने के लिए आपका वित्तीय डेटा एकत्र करते हैं। आपका डेटा भारतीय डेटा संरक्षण कानूनों के तहत सुरक्षित है।' },
  consent1: { en: 'I allow GraamCredit to access my bank/UPI transaction data for scoring purposes', hi: 'मैं ग्रामक्रेडिट को स्कोरिंग उद्देश्यों के लिए मेरे बैंक/UPI लेनदेन डेटा तक पहुंचने की अनुमति देता हूं' },
  consent2: { en: 'I allow verification of my government-issued ID for KYC compliance', hi: 'मैं KYC अनुपालन के लिए अपनी सरकारी आईडी के सत्यापन की अनुमति देता हूं' },
  consent3: { en: 'I agree to the Terms of Service and Privacy Policy of GraamCredit', hi: 'मैं ग्रामक्रेडिट की सेवा की शर्तों और गोपनीयता नीति से सहमत हूं' },
  // Step 2
  step2Title: { en: 'KYC / Personal Information', hi: 'KYC / व्यक्तिगत जानकारी' },
  step2Desc: { en: 'Tell us about yourself. All fields are required.', hi: 'हमें अपने बारे में बताएं। सभी फ़ील्ड आवश्यक हैं।' },
  securityNotice: { en: 'Your data is encrypted and stored securely', hi: 'आपका डेटा एन्क्रिप्टेड और सुरक्षित रूप से संग्रहीत है' },
  labelName: { en: 'Full Name', hi: 'पूरा नाम' },
  labelAge: { en: 'Age', hi: 'आयु' },
  labelGender: { en: 'Gender', hi: 'लिंग' },
  labelState: { en: 'State', hi: 'राज्य' },
  labelIdType: { en: 'ID Type', hi: 'आईडी प्रकार' },
  labelIdNumber: { en: 'ID Number', hi: 'आईडी नंबर' },
  labelEmail: { en: 'Email Address', hi: 'ईमेल पता' },
  // Step 3
  step3Title: { en: 'Financial Information', hi: 'वित्तीय जानकारी' },
  step3Desc: { en: 'Help us understand your financial situation.', hi: 'हमें अपनी वित्तीय स्थिति समझने में मदद करें।' },
  pdfUploadTitle: { en: 'Auto-fill from Bank Statement', hi: 'बैंक स्टेटमेंट से स्वतः भरें' },
  pdfUploadSub: { en: 'Upload your PDF statement to fill fields automatically. File is deleted immediately after parsing.', hi: 'फ़ील्ड स्वचालित रूप से भरने के लिए अपना PDF स्टेटमेंट अपलोड करें। पार्सिंग के बाद फ़ाइल तुरंत हटा दी जाती है।' },
  pdfDropText: { en: 'Click to select PDF (max 5 MB)', hi: 'PDF चुनने के लिए क्लिक करें (अधिकतम 5 MB)' },
  pdfDropSub: { en: 'SBI · HDFC · Axis · Canara · PNB · ICICI', hi: 'SBI · HDFC · Axis · Canara · PNB · ICICI' },
  pdfOrManual: { en: '— or fill manually below —', hi: '— या नीचे मैन्युअल रूप से भरें —' },
  aaTitle:    { en: 'Share Bank Data via Account Aggregator', hi: 'Account Aggregator के माध्यम से बैंक डेटा साझा करें' },
  aaSub:      { en: 'RBI-regulated consent flow. Your bank shares data directly — no password required. Powered by Setu AA.', hi: 'RBI-विनियमित सहमति प्रवाह। आपका बैंक सीधे डेटा साझा करता है — पासवर्ड की आवश्यकता नहीं। Setu AA द्वारा संचालित।' },
  aaBtnLabel: { en: 'Connect Bank', hi: 'बैंक कनेक्ट करें' },
  labelIncome: { en: 'Annual Household Income', hi: 'वार्षिक घरेलू आय' },
  labelExpenses: { en: 'Monthly Expenses', hi: 'मासिक खर्च' },
  labelLoans: { en: 'Existing Loans Count', hi: 'मौजूदा ऋण संख्या' },
  labelEMI: { en: 'Total Monthly EMI Obligations', hi: 'कुल मासिक EMI दायित्व' },
  labelEmployment: { en: 'Employment Type', hi: 'रोजगार का प्रकार' },
  labelSavings: { en: 'Current Bank Balance', hi: 'वर्तमान बैंक बैलेंस' },
  labelDependents: { en: 'Family Dependents', hi: 'परिवार के आश्रित' },
  // Step 4
  step4Title: { en: 'Digital Activity', hi: 'डिजिटल गतिविधि' },
  step4Desc: { en: 'Optional data that can help improve your score.', hi: 'वैकल्पिक डेटा जो आपके स्कोर को बेहतर बनाने में मदद कर सकता है।' },
  labelUPI: { en: 'UPI Transactions per Month', hi: 'प्रति माह UPI लेनदेन' },
  labelRecharges: { en: 'Mobile Recharges (last 6 months)', hi: 'मोबाइल रिचार्ज (पिछले 6 महीने)' },
  labelSHG: { en: 'Part of SHG/JLG Group?', hi: 'SHG/JLG समूह का सदस्य?' },
  infoNote: { en: 'This data helps us give you a better score. Filling these fields is optional but recommended.', hi: 'यह डेटा हमें आपको बेहतर स्कोर देने में मदद करता है। इन फ़ील्ड को भरना वैकल्पिक लेकिन अनुशंसित है।' },
  // Step 5
  step5Title: { en: 'Review Your Application', hi: 'अपना आवेदन समीक्षा करें' },
  step5Desc: { en: 'Please review all the information before submitting.', hi: 'कृपया सबमिट करने से पहले सभी जानकारी की समीक्षा करें।' },
  btnSubmit: { en: '🚀 Submit Application', hi: '🚀 आवेदन सबमिट करें' },
  btnNext: { en: 'Next →', hi: 'आगे →' },
  btnBack: { en: '← Back', hi: '← पीछे' },
  // Review labels
  revPersonal: { en: 'Personal Information', hi: 'व्यक्तिगत जानकारी' },
  revFinancial: { en: 'Financial Information', hi: 'वित्तीय जानकारी' },
  revDigital: { en: 'Digital Activity', hi: 'डिजिटल गतिविधि' },
  // Progress
  progressLabel: { en: 'Step', hi: 'चरण' },
  progressOf: { en: 'of', hi: 'का' },
};

function t(key) {
  return formTranslations[key] ? formTranslations[key][currentLang] : key;
}

function runInit() {
  initForm();
  applyFormLanguage();
}

if (document.readyState !== 'loading') {
  runInit();
} else {
  document.addEventListener('DOMContentLoaded', runInit);
}

function initForm() {
  showStep(1);
  updateProgressBar();
  setupConsentListeners();
  setupValidationListeners();
  _resumeAAIfRedirected();
  _prefillAATestPhone();
}

// ---- Test persona hand-off (test-personas.html → "Use this number") ----
function _prefillAATestPhone() {
  const params = new URLSearchParams(window.location.search);
  const phone = params.get('aa_test_phone');
  if (!phone) return;

  window.history.replaceState({}, '', window.location.pathname);

  const vuaInput = document.getElementById('aaVua');
  if (vuaInput) vuaInput.value = phone;

  showStep(3);
}

// ---- AA redirect resume ----
// When Setu bounces the user back to form.html?aa_session=xxx, auto-poll.
function _resumeAAIfRedirected() {
  const params    = new URLSearchParams(window.location.search);
  const sessionId = params.get('aa_session');
  if (!sessionId) return;

  // Remove the param so a manual refresh doesn't re-trigger
  const cleanUrl = window.location.pathname;
  window.history.replaceState({}, '', cleanUrl);

  // Show a persistent banner at the very top of the page
  const banner = document.createElement('div');
  banner.id = 'aaBanner';
  banner.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:9999',
    'background:#6366F1', 'color:#fff', 'text-align:center',
    'padding:10px 16px', 'font-size:0.9rem', 'font-weight:600',
  ].join(';');
  banner.innerHTML = '<i class="ri-loader-4-line"></i> Fetching your bank data… please wait.';
  document.body.prepend(banner);

  _pollAAWithBanner(sessionId, banner, 0);
}

async function _pollAAWithBanner(sessionId, banner, attempt) {
  const MAX_ATTEMPTS = 20;  // ~100 seconds
  const INTERVAL_MS  = 5000;

  if (attempt >= MAX_ATTEMPTS) {
    banner.style.background = '#ef4444';
    banner.innerHTML = '<i class="ri-error-warning-line"></i> Timed out waiting for bank data. Please go to Step 3 and use PDF upload or fill manually.';
    return;
  }

  try {
    const base  = window.GRAAMCREDIT_API || 'http://127.0.0.1:8000';
    const res   = await fetch(`${base}/api/aa/status/${sessionId}`);
    const data  = await res.json();

    if (data.status === 'fi_ready') {
      const fiRes = await fetch(`${base}/api/aa/fetch/${sessionId}`);
      const fi    = await fiRes.json();
      _autofillFromStatement(fi);

      banner.style.background = '#16a34a';
      banner.innerHTML = '<i class="ri-check-line"></i> Bank data received — fields auto-filled! <a href="#" onclick="showStep(3);this.closest(\'#aaBanner\').remove();return false;" style="color:#fff;text-decoration:underline;margin-left:8px;">Go to Step 3 to review →</a>';

    } else if (data.status === 'denied') {
      banner.style.background = '#ef4444';
      banner.innerHTML = '<i class="ri-close-circle-line"></i> Consent was denied. Please go to Step 3 and use PDF upload or fill manually.';
      setTimeout(() => banner.remove(), 8000);

    } else if (data.status === 'error') {
      banner.style.background = '#ef4444';
      banner.innerHTML = '<i class="ri-error-warning-line"></i> Could not fetch bank data. Please go to Step 3 and use PDF upload or fill manually.';
      setTimeout(() => banner.remove(), 8000);

    } else {
      // Still pending or approved-fetching — retry
      setTimeout(() => _pollAAWithBanner(sessionId, banner, attempt + 1), INTERVAL_MS);
    }
  } catch {
    // Network error — retry silently
    setTimeout(() => _pollAAWithBanner(sessionId, banner, attempt + 1), INTERVAL_MS);
  }
}

// ---- Progress Bar ----
function updateProgressBar() {
  const pct = ((currentStep - 1) / (totalSteps - 1)) * 100;
  const fill = document.getElementById('progressFill');
  if (fill) fill.style.width = pct + '%';

  // Update step label
  const labelEl = document.getElementById('progressStepLabel');
  if (labelEl) {
    const labels = stepLabels[currentLang];
    labelEl.textContent = labels[currentStep - 1];
  }

  // Update step count
  const countEl = document.getElementById('progressStepCount');
  if (countEl) {
    countEl.textContent = `${t('progressLabel')} ${currentStep} ${t('progressOf')} ${totalSteps}`;
  }

  // Update dots
  for (let i = 1; i <= totalSteps; i++) {
    const dot = document.getElementById(`stepDot${i}`);
    if (!dot) continue;
    dot.classList.remove('active', 'completed');
    if (i === currentStep) dot.classList.add('active');
    else if (i < currentStep) dot.classList.add('completed');
  }
}

// ---- Step Navigation ----
function showStep(step) {
  document.querySelectorAll('.form-step').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(`step${step}`);
  if (target) target.classList.add('active');
  currentStep = step;
  updateProgressBar();

  // Build review on step 5
  if (step === 5) buildReview();

  // Scroll to top of form
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function nextStep() {
  if (!validateStep(currentStep)) return;
  if (currentStep < totalSteps) showStep(currentStep + 1);
}

function prevStep() {
  if (currentStep > 1) showStep(currentStep - 1);
}

// ---- Consent Logic ----
function setupConsentListeners() {
  const checkboxes = document.querySelectorAll('.consent-checkbox input[type="checkbox"]');
  checkboxes.forEach(cb => {
    cb.addEventListener('change', () => {
      const parent = cb.closest('.consent-checkbox');
      if (cb.checked) parent.classList.add('checked');
      else parent.classList.remove('checked');
      updateConsentButton();
    });
  });
}

function updateConsentButton() {
  const allChecked = document.querySelectorAll('.consent-checkbox input[type="checkbox"]:checked').length === 3;
  const nextBtn = document.querySelector('#step1 .btn-proceed');
  if (nextBtn) nextBtn.disabled = !allChecked;
}

// ---- Validation ----
function setupValidationListeners() {
  // Clear errors on input
  document.querySelectorAll('.form-group input, .form-group select').forEach(field => {
    field.addEventListener('input', () => {
      field.classList.remove('error');
      const errMsg = field.parentElement.querySelector('.error-msg');
      if (errMsg) errMsg.classList.remove('visible');
    });
  });
}

function showError(fieldId, message) {
  const field = document.getElementById(fieldId);
  if (!field) return false;
  field.classList.add('error');
  const errMsg = field.parentElement.querySelector('.error-msg');
  if (errMsg) {
    errMsg.textContent = message;
    errMsg.classList.add('visible');
  }
  field.focus();
  return false;
}

function clearErrors() {
  document.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
  document.querySelectorAll('.error-msg').forEach(el => el.classList.remove('visible'));
}

function validateStep(step) {
  clearErrors();
  switch (step) {
    case 1:
      return document.querySelectorAll('.consent-checkbox input[type="checkbox"]:checked').length === 3;

    case 2: {
      const name = document.getElementById('fullName').value.trim();
      const age = parseInt(document.getElementById('age').value);
      const gender = document.getElementById('gender').value;
      const state = document.getElementById('state').value;
      const idType = document.getElementById('idType').value;
      const idNumber = document.getElementById('idNumber').value.trim();

      if (!name) return showError('fullName', currentLang === 'hi' ? 'कृपया अपना नाम दर्ज करें' : 'Please enter your full name');
      if (!age || age < 18) return showError('age', currentLang === 'hi' ? 'आयु 18 या अधिक होनी चाहिए' : 'Age must be 18 or above');
      if (age > 120) return showError('age', currentLang === 'hi' ? 'कृपया वैध आयु दर्ज करें' : 'Please enter a valid age');
      if (!gender) return showError('gender', currentLang === 'hi' ? 'कृपया लिंग चुनें' : 'Please select gender');
      if (!state) return showError('state', currentLang === 'hi' ? 'कृपया राज्य चुनें' : 'Please select state');
      if (!idType) return showError('idType', currentLang === 'hi' ? 'कृपया आईडी प्रकार चुनें' : 'Please select ID type');
      if (!idNumber) return showError('idNumber', currentLang === 'hi' ? 'कृपया आईडी नंबर दर्ज करें' : 'Please enter ID number');
      if (idType === 'aadhaar' && !/^\d{12}$/.test(idNumber)) return showError('idNumber', currentLang === 'hi' ? 'आधार 12 अंकों का होना चाहिए' : 'Aadhaar must be 12 digits');
      const emailVal = document.getElementById('applicantEmail')?.value?.trim();
      if (emailVal && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) return showError('applicantEmail', currentLang === 'hi' ? 'कृपया वैध ईमेल दर्ज करें' : 'Please enter a valid email address');
      return true;
    }

    case 3: {
      const income = parseFloat(document.getElementById('annualIncome').value);
      const expenses = parseFloat(document.getElementById('monthlyExpenses').value);
      const employment = document.getElementById('employment').value;

      if (!income || income <= 0) return showError('annualIncome', currentLang === 'hi' ? 'कृपया वैध आय दर्ज करें' : 'Please enter valid income');
      if (!expenses || expenses < 0) return showError('monthlyExpenses', currentLang === 'hi' ? 'कृपया वैध खर्च दर्ज करें' : 'Please enter valid expenses');
      if (!employment) return showError('employment', currentLang === 'hi' ? 'कृपया रोजगार प्रकार चुनें' : 'Please select employment type');
      return true;
    }

    case 4:
      return true; // optional

    case 5:
      return true;
  }
  return true;
}

// ---- Build Review ----
function buildReview() {
  const container = document.getElementById('reviewContent');
  if (!container) return;

  const data = getFormData();
  const genderMap = { female: 'Female / महिला', male: 'Male / पुरुष', other: 'Other / अन्य' };
  const idTypeMap = { aadhaar: 'Aadhaar Card', voter: 'Voter ID', nrega: 'NREGA Card' };
  const employmentMap = { salaried: 'Salaried / वेतनभोगी', farmer: 'Farmer / किसान', laborer: 'Daily Laborer / दैनिक मजदूर', business: 'Small Business / छोटा व्यापार', other: 'Other / अन्य' };

  container.innerHTML = `
    <div class="review-section">
      <h3>${t('revPersonal')}</h3>
      <div class="review-row"><span class="label">${t('labelName')}</span><span class="value">${data.fullName}</span></div>
      <div class="review-row"><span class="label">${t('labelAge')}</span><span class="value">${data.age}</span></div>
      <div class="review-row"><span class="label">${t('labelGender')}</span><span class="value">${genderMap[data.gender] || data.gender}</span></div>
      <div class="review-row"><span class="label">${t('labelState')}</span><span class="value">${data.state}</span></div>
      <div class="review-row"><span class="label">${t('labelIdType')}</span><span class="value">${idTypeMap[data.idType] || data.idType}</span></div>
      <div class="review-row"><span class="label">${t('labelIdNumber')}</span><span class="value">${maskId(data.idNumber)}</span></div>
      ${data.email ? `<div class="review-row"><span class="label">${t('labelEmail')}</span><span class="value">${data.email}</span></div>` : ''}
    </div>
    <div class="review-section">
      <h3>${t('revFinancial')}</h3>
      <div class="review-row"><span class="label">${t('labelIncome')}</span><span class="value">₹${Number(data.annualIncome).toLocaleString('en-IN')}</span></div>
      <div class="review-row"><span class="label">${t('labelExpenses')}</span><span class="value">₹${Number(data.monthlyExpenses).toLocaleString('en-IN')}/mo</span></div>
      <div class="review-row"><span class="label">${t('labelLoans')}</span><span class="value">${data.existingLoans}</span></div>
      <div class="review-row"><span class="label">${t('labelEMI')}</span><span class="value">₹${Number(data.monthlyEMI).toLocaleString('en-IN')}/mo</span></div>
      <div class="review-row"><span class="label">${t('labelEmployment')}</span><span class="value">${employmentMap[data.employment] || data.employment}</span></div>
      <div class="review-row"><span class="label">${t('labelSavings')}</span><span class="value">₹${Number(data.savingsBalance).toLocaleString('en-IN')}</span></div>
      <div class="review-row"><span class="label">${t('labelDependents')}</span><span class="value">${data.numDependents}</span></div>
    </div>
    <div class="review-section">
      <h3>${t('revDigital')}</h3>
      <div class="review-row"><span class="label">${t('labelUPI')}</span><span class="value">${data.upiTransactions}</span></div>
      <div class="review-row"><span class="label">${t('labelRecharges')}</span><span class="value">${data.mobileRecharges}</span></div>
      <div class="review-row"><span class="label">${t('labelSHG')}</span><span class="value">${data.inSHG ? '✓ Yes' : '✗ No'}</span></div>
    </div>
  `;
}

function maskId(idNum) {
  if (!idNum || idNum.length < 4) return idNum;
  return '●'.repeat(idNum.length - 4) + idNum.slice(-4);
}

// ---- Collect Form Data ----
function getFormData() {
  return {
    fullName: document.getElementById('fullName')?.value?.trim() || '',
    age: parseInt(document.getElementById('age')?.value) || 0,
    gender: document.getElementById('gender')?.value || '',
    state: document.getElementById('state')?.value || '',
    idType: document.getElementById('idType')?.value || '',
    idNumber: document.getElementById('idNumber')?.value?.trim() || '',
    annualIncome: parseFloat(document.getElementById('annualIncome')?.value) || 0,
    monthlyExpenses: parseFloat(document.getElementById('monthlyExpenses')?.value) || 0,
    existingLoans: parseInt(document.getElementById('existingLoans')?.value) || 0,
    monthlyEMI: parseFloat(document.getElementById('monthlyEMI')?.value) || 0,
    employment: document.getElementById('employment')?.value || '',
    savingsBalance: parseFloat(document.getElementById('savingsBalance')?.value) || 0,
    numDependents: parseInt(document.getElementById('numDependents')?.value) || 0,
    upiTransactions: parseInt(document.getElementById('upiTransactions')?.value) || 0,
    mobileRecharges: parseInt(document.getElementById('mobileRecharges')?.value) || 0,
    inSHG: document.getElementById('shgToggle')?.checked || false,
    email: document.getElementById('applicantEmail')?.value?.trim() || '',
  };
}

// ---- Submit Application (calls backend API) ----
async function submitApplication() {
  const data = getFormData();

  // Show loading overlay
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.classList.add('active');

  // Map frontend field names → backend snake_case names
  const payload = {
    name: data.fullName,
    age: data.age,
    gender: data.gender,
    state: data.state,
    id_type: data.idType,
    id_number: data.idNumber,
    annual_income: data.annualIncome,
    monthly_expenses: data.monthlyExpenses,
    existing_loans: data.existingLoans,
    monthly_emi: data.monthlyEMI,
    employment_type: data.employment,
    savings_balance: data.savingsBalance,
    num_dependents: data.numDependents,
    upi_transactions: data.upiTransactions,
    mobile_recharges: data.mobileRecharges,
    in_shg: data.inSHG,
    email: data.email || null,
  };

  // 10-second timeout so the loading overlay never hangs forever
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

  try {
    const response = await fetch((window.GRAAMCREDIT_API || 'http://127.0.0.1:8000') + '/api/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${response.status}`);
    }

    const result = await response.json();

    localStorage.setItem('graamcredit_appid', result.application_id);
    localStorage.setItem('graamcredit_result', JSON.stringify(result));
    localStorage.setItem('graamcredit_data', JSON.stringify(data));

    window.location.href = 'result.html';
  } catch (err) {
    clearTimeout(timeoutId);
    if (overlay) overlay.classList.remove('active');
    const isTimeout = err.name === 'AbortError';
    const msg = isTimeout
      ? 'The backend server did not respond in time.\n\nMake sure the server is running:\n  cd graamcredit-backend\n  python main.py'
      : 'Could not reach the backend server.\n\nSteps to fix:\n1. Open a terminal\n2. cd graamcredit-backend\n3. python main.py\n4. Then try again.\n\nError: ' + err.message;
    alert(currentLang === 'hi' ? 'सर्वर से कनेक्ट नहीं हो सका।\n\n' + err.message : msg);
  }
}

// ---- Language Hook (Form Page) ----
function applyFormLanguage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (formTranslations[key]) {
      el.textContent = formTranslations[key][currentLang];
    }
  });
  updateProgressBar();
  if (currentStep === 5) buildReview();
}

// ---- Account Aggregator (mock AA — see backend/routes/account_aggregator.py) ----
// Simulates the RBI-regulated consent flow end-to-end (no real Setu/Finvu call).

const _AA_BANK_ICONS = ['🏦 SBI', '🏛️ HDFC', '🏢 ICICI', '💠 Axis', '🏤 PNB'];

async function initiateAA() {
  const vua = document.getElementById('aaVua').value.trim();
  const statusEl = document.getElementById('aaStatus');

  if (!vua) {
    statusEl.style.display = 'block';
    statusEl.className = 'pdf-status error';
    statusEl.textContent = 'Please enter your mobile number or AA VUA (e.g. 9999999999@onemoney).';
    return;
  }

  statusEl.style.display = 'block';
  statusEl.className = 'pdf-status loading';
  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Creating consent request…';

  const btn = document.getElementById('aaBtn');
  btn.disabled = true;

  try {
    const base = window.GRAAMCREDIT_API || 'http://127.0.0.1:8000';
    const res = await fetch(`${base}/api/aa/initiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_id: vua }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();

    if (data.redirect_url) {
      // Real Setu mode (USE_MOCK_AA=false) — open the actual consent UI.
      window.open(data.redirect_url, '_blank', 'noopener');
      statusEl.className = 'pdf-status success';
      statusEl.innerHTML = `
        <i class="ri-check-line"></i>
        Consent page opened in a new tab. Approve it, then come back and click
        <strong>"Check Status"</strong> below.
        <br><br>
        <button type="button" onclick="pollAA('${data.session_id}')"
          style="background:#6366F1;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.82rem;">
          Check Status
        </button>`;
      return;
    }

    // Mock mode — show the simulated consent-approval card.
    _renderAAConsentCard(data.session_id);
  } catch (err) {
    statusEl.className = 'pdf-status error';
    statusEl.innerHTML = err.message.includes('not configured')
      ? '<i class="ri-error-warning-line"></i> Account Aggregator is not configured yet. Use PDF upload or fill manually.'
      : `<i class="ri-error-warning-line"></i> ${err.message}`;
    btn.disabled = false;
  }
}

function _renderAAConsentCard(sessionId) {
  const statusEl = document.getElementById('aaStatus');
  statusEl.className = 'pdf-status loading';
  statusEl.innerHTML = `
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;">
      ${_AA_BANK_ICONS.map(b => `<span style="background:#fff;border:1px solid #C7D2FE;border-radius:6px;padding:4px 10px;font-size:0.78rem;font-weight:600;color:#4338CA;">${b}</span>`).join('')}
    </div>
    <div style="font-weight:600;color:#4338CA;margin-bottom:6px;">
      <i class="ri-shield-check-line"></i> Consent request created — approve it on your Account Aggregator app.
    </div>
    <div style="font-size:0.8rem;color:#4B5563;margin-bottom:10px;">
      By approving, you allow GraamCredit to view (not control) your account statements for loan underwriting only.
    </div>
    <button type="button" id="aaApproveBtn" onclick="approveAA('${sessionId}')"
      style="background:#16a34a;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-weight:600;font-size:0.85rem;cursor:pointer;">
      <i class="ri-checkbox-circle-line"></i> Approve consent request
    </button>`;
}

async function approveAA(sessionId) {
  const statusEl = document.getElementById('aaStatus');
  const approveBtn = document.getElementById('aaApproveBtn');
  if (approveBtn) approveBtn.disabled = true;

  statusEl.className = 'pdf-status loading';
  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Waiting for your bank to confirm consent…';

  try {
    const base = window.GRAAMCREDIT_API || 'http://127.0.0.1:8000';
    const res = await fetch(`${base}/api/aa/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();

    if (data.status === 'error') {
      statusEl.className = 'pdf-status error';
      statusEl.innerHTML = `
        <i class="ri-error-warning-line"></i> ${data.message || 'Could not confirm consent with your bank.'}
        <br><br>
        <button type="button" onclick="approveAA('${sessionId}')"
          style="background:#6366F1;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.82rem;">
          Retry
        </button>`;
      return;
    }

    const [accountsRes, fiRes] = await Promise.all([
      fetch(`${base}/api/aa/accounts/${sessionId}`),
      fetch(`${base}/api/aa/fetch/${sessionId}`),
    ]);
    const accountsData = await accountsRes.json();
    const fi = await fiRes.json();

    _autofillFromStatement(fi);

    const acct = accountsData.accounts && accountsData.accounts[0];
    const acctLine = acct ? `${acct.bank_name} · ${acct.account_masked}` : 'your linked bank account';

    statusEl.className = 'pdf-status success';
    statusEl.innerHTML = `
      <i class="ri-check-line"></i> Data fetched successfully from <strong>${acctLine}</strong>.
      Fields below have been auto-filled — please verify.`;
  } catch (err) {
    statusEl.className = 'pdf-status error';
    statusEl.innerHTML = `<i class="ri-error-warning-line"></i> ${err.message || 'Something went wrong. Please try again.'}
      <br><br>
      <button type="button" onclick="approveAA('${sessionId}')"
        style="background:#6366F1;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.82rem;">
        Retry
      </button>`;
  }
}

async function pollAA(sessionId) {
  // Real Setu mode only (USE_MOCK_AA=false) — mock mode uses approveAA() above.
  const statusEl = document.getElementById('aaStatus');
  statusEl.className = 'pdf-status loading';
  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Checking consent status…';

  try {
    const base = window.GRAAMCREDIT_API || 'http://127.0.0.1:8000';
    const res = await fetch(`${base}/api/aa/status/${sessionId}`);
    const data = await res.json();

    if (data.status === 'fi_ready') {
      const fiRes = await fetch(`${base}/api/aa/fetch/${sessionId}`);
      const fi = await fiRes.json();
      _autofillFromStatement(fi);
      statusEl.className = 'pdf-status success';
      statusEl.innerHTML = '<i class="ri-check-line"></i> Bank data received and fields filled. Please verify.';
    } else if (data.status === 'denied') {
      statusEl.className = 'pdf-status error';
      statusEl.innerHTML = '<i class="ri-close-circle-line"></i> Consent was denied. Please use PDF upload or fill manually.';
      document.getElementById('aaBtn').disabled = false;
    } else if (data.status === 'error') {
      statusEl.className = 'pdf-status error';
      statusEl.innerHTML = '<i class="ri-error-warning-line"></i> Could not fetch data from bank. Try PDF upload instead.';
      document.getElementById('aaBtn').disabled = false;
    } else {
      // Still pending or approved-but-fetching — let user retry
      statusEl.className = 'pdf-status loading';
      statusEl.innerHTML = `
        <i class="ri-loader-4-line"></i> ${data.message}
        <br><br>
        <button type="button" onclick="pollAA('${sessionId}')"
          style="background:#6366F1;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.82rem;">
          Check Again
        </button>`;
    }
  } catch {
    statusEl.className = 'pdf-status error';
    statusEl.innerHTML = '<i class="ri-error-warning-line"></i> Status check failed. Is the backend running?';
  }
}

// ---- PDF Statement Upload & Auto-fill ----

const _autofillFields = new Set();

async function handlePDFUpload(file) {
  if (!file) return;

  const statusEl = document.getElementById('pdfStatus');
  statusEl.style.display = 'block';
  statusEl.className = 'pdf-status loading';
  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Parsing statement… please wait';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${window.GRAAMCREDIT_API || 'http://127.0.0.1:8000'}/api/parse-statement`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    _autofillFromStatement(data);

    const pct = Math.round(data.confidence * 100);
    statusEl.className = 'pdf-status success';
    statusEl.innerHTML = `<i class="ri-check-line"></i> Fields filled from statement (${pct}% confidence). Please verify the values below.`;
  } catch (err) {
    statusEl.className = 'pdf-status error';
    statusEl.innerHTML = `<i class="ri-error-warning-line"></i> ${
      err.message.includes('fetch') || err.name === 'TypeError'
        ? 'Backend not reachable. Fill fields manually.'
        : err.message
    }`;
  }
}

function _autofillFromStatement(data) {
  const map = {
    annualIncome:    data.annual_income,
    monthlyExpenses: data.monthly_expenses,
    savingsBalance:  data.savings_balance,
    monthlyEMI:      data.monthly_emi,
    existingLoans:   data.existing_loans,
    upiTransactions: data.upi_transactions,
    mobileRecharges: data.mobile_recharges,
  };

  _autofillFields.clear();

  for (const [fieldId, value] of Object.entries(map)) {
    if (value === undefined || value === null) continue;
    const el = document.getElementById(fieldId);
    if (!el) continue;

    // Only autofill non-zero values; don't overwrite what the user typed
    if (value > 0 || fieldId === 'existingLoans') {
      el.value = value;
      el.classList.remove('error');
      _markAutofilled(el);
      _autofillFields.add(fieldId);
    }
  }
}

function _markAutofilled(inputEl) {
  // Add a green "auto-filled" badge next to the label
  const formGroup = inputEl.closest('.form-group');
  if (!formGroup) return;
  const label = formGroup.querySelector('label');
  if (!label) return;
  // Remove any existing badge first
  const existing = label.querySelector('.autofilled-badge');
  if (existing) existing.remove();
  const badge = document.createElement('span');
  badge.className = 'autofilled-badge';
  badge.textContent = '✓ auto-filled';
  label.appendChild(badge);
}

// Remove auto-fill badges when user edits the field manually
document.addEventListener('DOMContentLoaded', () => {
  ['annualIncome', 'monthlyExpenses', 'savingsBalance', 'monthlyEMI',
   'existingLoans', 'upiTransactions', 'mobileRecharges'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => {
      if (!_autofillFields.has(id)) return;
      const label = el.closest('.form-group')?.querySelector('label');
      label?.querySelector('.autofilled-badge')?.remove();
      _autofillFields.delete(id);
    });
  });
});

document.addEventListener('languageChanged', (e) => {
  currentLang = e.detail.lang;
  applyFormLanguage();
});

