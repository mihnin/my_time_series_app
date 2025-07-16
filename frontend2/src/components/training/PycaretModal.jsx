import React from 'react';

export default function PycaretModal({
  visible,
  closeModal,
  pycaretLeaderboards,
  formatCellValue
}) {
  if (!visible) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={closeModal}>
      <div 
        className="bg-white rounded-lg p-6 max-w-4xl max-h-[80vh] overflow-y-auto shadow-xl relative border border-gray-200" 
        onClick={(e) => e.stopPropagation()}
      >
        <button 
          className="absolute top-2 right-3 text-gray-500 hover:text-red-600 text-2xl font-bold"
          onClick={closeModal}
        >
          ×
        </button>
        <h3 className="text-xl font-bold mb-4">Лидерборды PyCaret</h3>
        {pycaretLeaderboards && typeof pycaretLeaderboards === 'object' ? (
          <div className="space-y-6">
            {Object.entries(pycaretLeaderboards).map(([id, lbArr]) => (
              <div key={id} className="border border-gray-200 rounded-lg p-4">
                <h4 className="text-lg font-semibold mb-3">ID: {id}</h4>
                {Array.isArray(lbArr) && lbArr.length > 0 ? (
                  typeof lbArr[0] === 'object' && lbArr[0] !== null ? (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse border border-gray-300">
                        <thead>
                          <tr className="bg-gray-50">
                            {Object.keys(lbArr[0]).map((key) => (
                              <th key={key} className="border border-gray-300 px-3 py-2 text-left font-medium">
                                {key}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {lbArr.map((row, ridx) => (
                            <tr key={ridx} className="hover:bg-gray-50">
                              {Object.entries(row).map(([key, value]) => (
                                <td key={key} className="border border-gray-300 px-3 py-2 text-center">
                                  {formatCellValue(key, value)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-red-600 text-center py-2">Нет данных по моделям</div>
                  )
                ) : (
                  <div className="text-red-600 text-center py-2">Нет данных по моделям</div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-red-600 text-center">Нет данных PyCaret</div>
        )}
      </div>
    </div>
  );
} 