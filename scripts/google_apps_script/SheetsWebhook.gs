// Deploy this file as a Web App. Configure Script Properties, never source secrets.
function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const props = PropertiesService.getScriptProperties();
    const body = JSON.parse(e.postData.contents);
    const secret = props.getProperty('SHEETS_WEBHOOK_SECRET');
    if (!secret || secret.length < 24 || body.secret !== secret) throw new Error('Unauthorized');
    if (!Array.isArray(body.values) || body.values.length !== 8 ||
        typeof body.values[0] !== 'string' || !body.values[0]) throw new Error('Invalid values');
    lock.waitLock(20000);
    const sheet = SpreadsheetApp.openById(props.getProperty('SPREADSHEET_ID')).getSheetByName('Expenses');
    if (!sheet) throw new Error('Missing Expenses sheet');
    // Upsert by immutable expense ID, even after a user sorts the sheet.
    const count = sheet.getLastRow();
    const ids = count > 1 ? sheet.getRange(2, 1, count - 1, 1).getValues() : [];
    const index = ids.findIndex(row => String(row[0]) === body.values[0]);
    const row = index < 0 ? Math.max(2, count + 1) : index + 2;
    const values = body.values.map((value, i) => {
      if (value === null) return '';
      if (i === 6 && value !== '' && Number.isFinite(Number(value))) return Number(value);
      const text = String(value);
      return /^\s*[=+@-]/.test(text) ? "'" + text : text;
    });
    sheet.getRange(row, 1, 1, 8).setValues([values]);
    SpreadsheetApp.flush();
    return reply({status: 'ok', id: body.values[0]});
  } catch (err) {
    // ContentService may still return HTTP 200; backend checks this status.
    return reply({status: 'error'});
  } finally {
    if (lock.hasLock()) lock.releaseLock();
  }
}

function reply(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}
