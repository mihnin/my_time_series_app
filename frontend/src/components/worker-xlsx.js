// worker-xlsx.js
importScripts('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js');

self.onmessage = function(e) {
  const { fileData, fileName, maxRows } = e.data;
  try {
    const workbook = XLSX.read(fileData, { type: 'binary' });
    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
    let jsonData = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
    if (maxRows && jsonData.length > maxRows) {
      jsonData = jsonData.slice(0, maxRows);
    }
    // Convert back to objects using first row as header
    const [header, ...rows] = jsonData;
    const result = rows.map(row => {
      const obj = {};
      header.forEach((key, idx) => {
        obj[key] = row[idx];
      });
      return obj;
    });
    self.postMessage({ success: true, data: result });
  } catch (error) {
    self.postMessage({ success: false, error: error.message });
  }
};
