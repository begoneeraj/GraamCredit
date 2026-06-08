/* =============================================
   GraamCredit — result.js
   Renders the eligibility result from localStorage
   ============================================= */

// currentLang is declared as a global var in lang-config.js — no re-declaration needed.

document.addEventListener('languageChanged', function(e) {
  currentLang = e.detail.lang;
  renderResult();
});

// Guard against DOMContentLoaded race condition:
// Since this script loads at end of body, DOM is already ready.
if (document.readyState !== 'loading') {
  renderResult();
} else {
  document.addEventListener('DOMContentLoaded', renderResult);
}

function renderResult() {
  var resultStr = localStorage.getItem('graamcredit_result');
  var dataStr   = localStorage.getItem('graamcredit_data');
  var card = document.getElementById('resultCard');
  if (!card) return;

  if (!resultStr) {
    card.innerHTML =
      '<div class="result-icon" style="background: var(--warning-light); color: var(--warning);">⚠️</div>' +
      '<h1 style="color: var(--text-dark);">' + (currentLang === 'hi' ? 'कोई आवेदन नहीं मिला' : 'No Application Found') + '</h1>' +
      '<p class="result-subtitle">' + (currentLang === 'hi' ? 'कृपया पहले आवेदन पत्र भरें।' : 'Please complete the application form first.') + '</p>' +
      '<div class="result-actions"><a href="form.html" class="btn btn-primary btn-lg">' + (currentLang === 'hi' ? 'आवेदन शुरू करें' : 'Start Application') + '</a></div>';
    return;
  }

  var result = JSON.parse(resultStr);
  var data = dataStr ? JSON.parse(dataStr) : {};
  var applicantName = result.name || data.fullName || 'Applicant';

  if (result.eligible) {
    renderApproved(card, result, applicantName);
  } else {
    renderRejected(card, result, applicantName);
  }
}

function renderApproved(card, result, applicantName) {
  var score = result.score;
  var en = currentLang === 'en';

  var reasons = result.reasons || [];
  var breakdownHTML = reasons.map(function(r) {
    return '<tr><td>' + r.rule + '</td><td class="' + (r.passed ? 'status-pass' : 'status-fail') + '">' + (r.passed ? '✓' : '✗') + '</td><td style="font-size:0.8rem;color:var(--text-light)">' + (r.detail || '') + '</td></tr>';
  }).join('');

  var loanAmount = result.max_loan_amount
    ? '₹' + Number(result.max_loan_amount).toLocaleString('en-IN')
    : '₹25,000';

  card.className = 'result-card approved';
  card.innerHTML =
    '<div class="result-icon">✓</div>' +
    '<h1>' + (en ? 'Pre-Qualified!' : 'पूर्व-योग्य!') + '</h1>' +
    '<p class="result-subtitle">' + (en
      ? 'Congratulations, <strong>' + applicantName + '</strong>! You may be eligible for a microloan up to <strong>' + loanAmount + '</strong>'
      : 'बधाई, <strong>' + applicantName + '</strong>! आप <strong>' + loanAmount + '</strong> तक के माइक्रोलोन के लिए पात्र हो सकते हैं') + '</p>' +
    '<div class="score-section">' +
      '<div class="score-header">' +
        '<span class="score-label">' + (en ? 'GraamCredit Score' : 'ग्रामक्रेडिट स्कोर') + '</span>' +
        '<span class="score-value" id="scoreDisplay">0</span>' +
      '</div>' +
      '<div class="score-bar-track"><div class="score-bar-fill" id="scoreFill" style="width: 0%"></div></div>' +
      '<div class="score-labels"><span>0</span><span>' + (en ? 'Poor' : 'कम') + '</span><span>' + (en ? 'Average' : 'औसत') + '</span><span>' + (en ? 'Good' : 'अच्छा') + '</span><span>100</span></div>' +
    '</div>' +
    '<div class="chart-section">' +
      '<h3>' + (en ? 'Your Score vs Benchmarks' : 'आपका स्कोर बनाम बेंचमार्क') + '</h3>' +
      '<div class="chart-bars">' +
        '<div class="chart-bar-row"><span class="chart-bar-label">' + (en ? 'Your Score' : 'आपका स्कोर') + '</span><div class="chart-bar-track"><div class="chart-bar-fill user" id="chartUser" style="width: 0%"></div></div></div>' +
        '<div class="chart-bar-row"><span class="chart-bar-label">' + (en ? 'Avg. Applicant' : 'औसत आवेदक') + '</span><div class="chart-bar-track"><div class="chart-bar-fill average" id="chartAvg" style="width: 0%">55</div></div></div>' +
        '<div class="chart-bar-row"><span class="chart-bar-label">' + (en ? 'Min. Required' : 'न्यूनतम आवश्यक') + '</span><div class="chart-bar-track"><div class="chart-bar-fill min" id="chartMin" style="width: 0%">40</div></div></div>' +
      '</div>' +
    '</div>' +
    '<table class="breakdown-table"><thead><tr><th>' + (en ? 'Eligibility Rule' : 'पात्रता नियम') + '</th><th>' + (en ? 'Status' : 'स्थिति') + '</th><th>' + (en ? 'Detail' : 'विवरण') + '</th></tr></thead><tbody>' + breakdownHTML + '</tbody></table>' +
    '<div class="result-actions">' +
      '<button class="btn btn-primary btn-lg" onclick="alert(\'' + (en ? 'This would redirect to the full application on a partner bank\'s portal.' : 'यह एक पार्टनर बैंक के पोर्टल पर पूर्ण आवेदन पर रीडायरेक्ट करेगा।') + '\')">' + (en ? 'Proceed to Full Application →' : 'पूर्ण आवेदन पर आगे बढ़ें →') + '</button>' +
      '<button class="btn btn-print btn-sm" onclick="window.print()">🖨️ ' + (en ? 'Print / Save as PDF' : 'प्रिंट / PDF सहेजें') + '</button>' +
      '<a href="form.html" class="btn btn-outline btn-sm">' + (en ? 'Apply Again' : 'फिर से आवेदन करें') + '</a>' +
    '</div>';

  setTimeout(function() {
    var fill = document.getElementById('scoreFill');
    var chartUser = document.getElementById('chartUser');
    var chartAvg = document.getElementById('chartAvg');
    var chartMin = document.getElementById('chartMin');
    if (fill) fill.style.width = score + '%';
    if (chartUser) { chartUser.style.width = score + '%'; chartUser.textContent = score; }
    if (chartAvg) chartAvg.style.width = '55%';
    if (chartMin) chartMin.style.width = '40%';
    animateCounter('scoreDisplay', 0, score, 1200);
  }, 100);
}

function renderRejected(card, result, applicantName) {
  var en = currentLang === 'en';

  var failedRule = (result.reasons || []).find(function(r) { return !r.passed; });
  var reason = failedRule ? failedRule.detail : ((result.improvement_tips && result.improvement_tips[0]) || 'Does not meet eligibility criteria.');

  var tips = (result.improvement_tips && result.improvement_tips.length)
    ? result.improvement_tips
    : [
        en ? 'Clear any existing loans before re-applying' : 'पुनः आवेदन करने से पहले मौजूदा ऋणों को चुकाएं',
        en ? 'Reduce monthly expenses to improve your debt-to-income ratio' : 'अपने ऋण-से-आय अनुपात को बेहतर बनाने के लिए मासिक खर्च कम करें',
        en ? 'Increase digital transactions (UPI) to build financial history' : 'डिजिटल वित्तीय इतिहास बनाने के लिए UPI लेनदेन बढ़ाएं',
        en ? 'Join a Self Help Group (SHG) or Joint Liability Group (JLG)' : 'स्वयं सहायता समूह (SHG) या JLG से जुड़ें',
        en ? 'Wait 3–6 months and re-apply after improving your financial profile' : '3–6 महीने बाद अपनी वित्तीय प्रोफ़ाइल सुधारकर पुनः आवेदन करें',
      ];

  var tipsIcons = ['📋', '💰', '📱', '🤝', '🕐'];
  var tipsHTML = tips.map(function(tip, i) {
    return '<li><span class="tip-icon">' + tipsIcons[i % tipsIcons.length] + '</span><span>' + tip + '</span></li>';
  }).join('');

  card.className = 'result-card rejected';
  card.innerHTML =
    '<div class="result-icon">✗</div>' +
    '<h1>' + (en ? 'Not Eligible Right Now' : 'अभी पात्र नहीं') + '</h1>' +
    '<p class="result-subtitle">' + (en
      ? 'Sorry, <strong>' + applicantName + '</strong>. Based on the information provided, you don\'t currently meet the eligibility criteria.'
      : 'क्षमा करें, <strong>' + applicantName + '</strong>। दी गई जानकारी के आधार पर, आप वर्तमान में पात्रता मानदंडों को पूरा नहीं करते।') + '</p>' +
    '<div class="rejection-reason"><h3>' + (en ? '❌ Primary Reason' : '❌ मुख्य कारण') + '</h3><p>' + reason + '</p></div>' +
    '<div class="tips-section"><h3>' + (en ? '💡 Tips to Improve Eligibility' : '💡 पात्रता सुधारने के सुझाव') + '</h3><ul>' + tipsHTML + '</ul></div>' +
    '<div class="result-actions">' +
      '<a href="form.html" class="btn btn-danger btn-lg">' + (en ? 'Try Again →' : 'फिर से प्रयास करें →') + '</a>' +
      '<a href="index.html" class="btn btn-outline btn-sm">' + (en ? 'Back to Home' : 'होम पर वापस जाएं') + '</a>' +
    '</div>';
}

function animateCounter(elementId, start, end, duration) {
  var el = document.getElementById(elementId);
  if (!el) return;
  var range = end - start;
  var startTime = performance.now();
  function update(currentTime) {
    var elapsed = currentTime - startTime;
    var progress = Math.min(elapsed / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(start + range * eased);
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}
