const ZONE_X = [
    // { from: cột bắt đầu, to: cột kết thúc, scale: hệ số phóng }
    { from: 0, to: 1000, scale: 1 }  // Mặc định toàn bộ
];
const ZONE_Y = [
    { from: 0, to: 353, scale: 1 },  // Bình thường
    { from: 353, to: 353 + 18, scale: 4 },  // Vùng có slot → phóng 4x
    { from: 353 + 40 * 1, to: 353 + 18 + 40 * 1, scale: 4 },
    { from: 353 + 40 * 2, to: 353 + 18 + 40 * 2, scale: 4 },
    { from: 353 + 40 * 3, to: 353 + 18 + 40 * 3, scale: 4 },
    { from: 353 + 40 * 4, to: 353 + 18 + 40 * 4, scale: 4 },
    { from: 353 + 40 * 5, to: 353 + 18 + 40 * 5, scale: 4 },
    { from: 353 + 40 * 6, to: 353 + 18 + 40 * 6, scale: 4 },
    { from: 353 + 40 * 7, to: 353 + 18 + 40 * 7, scale: 4 },
    { from: 353 + 40 * 8, to: 353 + 18 + 40 * 8, scale: 4 },
    { from: 353 + 40 * 9, to: 353 + 18 + 40 * 9, scale: 4 },
    { from: 353 + 40 * 10, to: 353 + 18 + 40 * 10, scale: 4 },
    { from: 353 + 18 + 40 * 10, to: 774, scale: 1 },
    { from: 775, to: 780, scale: 3 },
    { from: 780, to: 740 + 40 + 3, scale: 1 },
    { from: 740 + 40 + 3, to: 740 + 40 + 3 + 18, scale: 4 },
    { from: 740 + 40 + 3 + 18, to: 740 + 40 + 33, scale: 4 },
    { from: 740 + 40 + 33, to: 740 + 40 + 33 + 18 + 3, scale: 4 },
    { from: 740 + 40 + 33 + 18 + 3, to: 851, scale: 4 },
    { from: 852, to: 1000, scale: 1 },
];