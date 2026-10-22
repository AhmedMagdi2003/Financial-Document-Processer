// Standalone Apps Script project. See docs/INTEGRATION_GUIDE.md for properties.
function processNewInvoices() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const base = (props.getProperty('API_BASE_URL') || '').replace(/\/$/, '');
    if (!/^https:\/\//.test(base)) throw new Error('Configure public HTTPS API_BASE_URL');
    const project = props.getProperty('PROJECT_ID');
    const token = props.getProperty('REVIEWER_TOKEN');
    if (!project || !token) throw new Error('Configure PROJECT_ID and REVIEWER_TOKEN');
    const request = (path, options) => {
      options = Object.assign({method: 'get'}, options || {});
      options.headers = Object.assign({
        Authorization: 'Bearer ' + token,
        'ngrok-skip-browser-warning': 'true'
      }, options.headers || {});
      options.muteHttpExceptions = true;
      options.followRedirects = false;
      const response = UrlFetchApp.fetch(base + path, options);
      if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
        throw new Error('HTTP ' + response.getResponseCode());
      }
      return JSON.parse(response.getContentText());
    };
    const folder = DriveApp.getFolderById(props.getProperty('FOLDER_ID'));
    let files;
    try {
      const cursor = props.getProperty('DRIVE_CURSOR');
      files = cursor ? DriveApp.continueFileIterator(cursor) : folder.getFiles();
    } catch (err) { files = folder.getFiles(); }
    const started = Date.now();
    let handled = 0;
    while (files.hasNext() && handled < 2 && Date.now() - started < 180000) {
      const file = files.next();
      if (!['application/pdf', 'image/jpeg', 'image/png', 'image/webp'].includes(file.getMimeType())) continue;
      if (file.getSize() > Number(props.getProperty('MAX_FILE_BYTES') || 10485760)) continue;
      const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,
        project + ':' + file.getId() + ':' + file.getLastUpdated().getTime());
      const key = 'drive-' + Utilities.base64EncodeWebSafe(digest).replace(/=+$/, '');
      const saved = JSON.parse(props.getProperty(key) || '{}');
      if (saved.done || saved.paused || (saved.nextAttempt || 0) > Date.now()) continue;
      handled++;
      try {
        let doc;
        if (saved.documentId) {
          doc = request('/api/v1/documents/' + encodeURIComponent(saved.documentId)).document;
          if (doc.state === 'FAILED') {
            if ((saved.retries || 0) >= 3) { saved.paused = true; }
            else {
              saved.retries = (saved.retries || 0) + 1;
              props.setProperty(key, JSON.stringify(saved));
              doc = request('/api/v1/documents/' + encodeURIComponent(saved.documentId) + '/reextract', {method: 'post'});
            }
          }
        } else {
          const result = request('/api/v1/documents', {
            method: 'post', headers: {'Idempotency-Key': key},
            payload: {file: file.getBlob(), project_id: project,
              auto_record: props.getProperty('AUTO_RECORD') === 'true' ? 'true' : 'false'}
          });
          doc = result.document;
        }
        if (!doc || !doc.id || !doc.state) throw new Error('Invalid document response');
        saved.documentId = doc.id;
        saved.state = doc.state;
        saved.done = ['RECORDED', 'DISMISSED'].includes(doc.state);
        saved.nextAttempt = Date.now() + 5 * 60 * 1000;
        saved.errors = 0;
        console.log(file.getId() + ': ' + doc.state + ' (' + doc.id + ')');
      } catch (err) {
        saved.errors = (saved.errors || 0) + 1;
        saved.nextAttempt = Date.now() + Math.min(60, Math.pow(2, saved.errors)) * 60000;
        if (saved.errors >= 5) saved.paused = true;
        console.warn(file.getId() + ': retry delayed; inspect API and script execution logs');
      }
      props.setProperty(key, JSON.stringify(saved));
    }
    if (files.hasNext()) props.setProperty('DRIVE_CURSOR', files.getContinuationToken());
    else props.deleteProperty('DRIVE_CURSOR');
  } finally { lock.releaseLock(); }
}

function installDriveTrigger() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'processNewInvoices')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('processNewInvoices').timeBased().everyMinutes(1).create();
}

// Run this function anytime to trigger instant processing without waiting for the 1-minute trigger
function syncNow() {
  processNewInvoices();
}
