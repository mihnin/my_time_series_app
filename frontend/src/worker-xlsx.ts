import * as XLSX from 'xlsx';

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
      const obj: Record<string, any> = {};
      header.forEach((key: string, idx: number) => {
        obj[key] = row[idx];
      });
      return obj;
    });
    self.postMessage({ success: true, data: result });
  } catch (error: any) {
    self.postMessage({ success: false, error: error.message });
  }
};
