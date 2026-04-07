const MAP_DATA = {
    width: 1000, height: 1000,
    layers: [
        {
            name: "", type: "dirt",
            rects: [
                { x: 129, y: 350 + 40 * 0, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 0, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 0, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 0, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 1, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 1, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 1, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 1, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 2, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 2, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 2, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 2, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 3, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 3, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 3, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 3, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 4, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 4, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 4, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 4, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 5, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 5, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 5, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 5, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 6, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 6, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 6, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 6, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 7, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 7, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 7, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 7, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 8, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 8, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 8, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 8, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 9, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 9, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 9, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 9, w: 180, h: 25 },

                { x: 129, y: 350 + 40 * 10, w: 176, h: 25 },
                { x: 333, y: 350 + 40 * 10, w: 178, h: 25 },
                { x: 538, y: 350 + 40 * 10, w: 179, h: 25 },
                { x: 743, y: 350 + 40 * 10, w: 180, h: 25 },

                { x: 123, y: 780, w: 26, h: 145 },
                { x: 160, y: 780, w: 30, h: 115 },
                { x: 201, y: 780, w: 40, h: 75 },
                { x: 251, y: 780, w: 54, h: 54 },

                { x: 333, y: 780, w: 196, h: 43 },
                { x: 539, y: 780, w: 177, h: 25 },
                { x: 539, y: 810, w: 177, h: 25 },

            ]
        },
        {
            name: "Đường nội bộ", type: "road", passable: true,
            rects: [
                { x: 101, y: 40, w: 28, h: 740 },
                { x: 305, y: 40, w: 28, h: 740 },
                { x: 511, y: 40, w: 28, h: 740 },
                { x: 716, y: 40, w: 28, h: 740 },
                { x: 922, y: 40, w: 28, h: 740 },

                { x: 128, y: 40, w: 178, h: 15 },
                { x: 332, y: 40, w: 180, h: 15 },
                { x: 538, y: 40, w: 179, h: 15 },
                { x: 743, y: 40, w: 180, h: 15 },

                { x: 101, y: 335 + 40 * 0, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 1, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 2, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 3, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 4, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 5, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 6, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 7, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 8, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 9, w: 850, h: 15 },
                { x: 101, y: 335 + 40 * 10, w: 850, h: 15 },

                { x: 105, y: 740 + 40 - 5, w: 18, h: 150 },
                { x: 149, y: 740 + 40 - 5, w: 11, h: 150 },
                { x: 105, y: 740 + 40 + 150 - 5, w: 55, h: 5 },

                { x: 190, y: 740 + 40 - 5, w: 11, h: 120 },
                { x: 149, y: 740 + 40 + 120 - 5, w: 52, h: 5 },

                { x: 241, y: 740 + 40 - 5, w: 10, h: 80 },
                { x: 190, y: 740 + 40 + 80 - 5, w: 61, h: 5 },

                { x: 305, y: 740 + 40 - 5, w: 28, h: 105 },
                { x: 716, y: 740 + 40 - 5, w: 45, h: 125 },

                { x: 529, y: 740 + 40 - 5, w: 10, h: 60 },
                // { x: 716, y: 740 + 40, w: 5, h: 60 },
                { x: 529, y: 740 + 95, w: 232, h: 5 },
                { x: 529, y: 740 + 40 + 25, w: 232, h: 5 },

                { x: 101, y: 335 + 40 * 11, w: 850, h: 5 },

            ]
        },
        {
            name: "", type: "crane",
            rects: [
                { x: 216, y: 40, w: 13, h: 15 },
                { x: 216 + 13 * 2, y: 40, w: 13, h: 15 },
                { x: 216 + 13 * 4, y: 40, w: 13, h: 15 },
                { x: 216 + 13 * 6, y: 40, w: 13, h: 15 },
                { x: 655, y: 40, w: 13, h: 15 },
                { x: 655 + 13 * 2, y: 40, w: 13, h: 15 },
                { x: 655 + 13 * 4, y: 40, w: 13, h: 15 },
                { x: 832, y: 40, w: 13, h: 15 },
                { x: 832 + 13 * 2, y: 40, w: 13, h: 15 },
                { x: 832 + 13 * 4, y: 40, w: 13, h: 15 },
            ]
        },
        {
            name: "Bờ cỏ", type: "grass",
            rects: [
                { x: 100 + 23 + 5 + 5, y: 50 + 5 + 5 + 200 + 10, w: 178 - 10, h: 60 },
                { x: 305 + 23 + 5 + 5, y: 50 + 5 + 5 + 200 + 10, w: 178 - 10, h: 60 },
                { x: 511 + 23 + 5 + 5, y: 50 + 5 + 5 + 200 + 10, w: 178 - 10, h: 60 },
                { x: 716 + 23 + 5 + 5, y: 50 + 5 + 5 + 200 + 10, w: 178 - 10, h: 60 },
            ]
        },
    ],
    blocks: [
        { prefix: "AK", x: 132, y: 353, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BK", x: 337, y: 353, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CK", x: 543, y: 353, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DK", x: 748, y: 353, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AJ", x: 132, y: 353 + 40 * 1, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BJ", x: 337, y: 353 + 40 * 1, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CJ", x: 543, y: 353 + 40 * 1, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DJ", x: 748, y: 353 + 40 * 1, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AI", x: 132, y: 353 + 40 * 2, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BI", x: 337, y: 353 + 40 * 2, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CI", x: 543, y: 353 + 40 * 2, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DI", x: 748, y: 353 + 40 * 2, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AH", x: 132, y: 353 + 40 * 3, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BH", x: 337, y: 353 + 40 * 3, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CH", x: 543, y: 353 + 40 * 3, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DH", x: 748, y: 353 + 40 * 3, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AG", x: 132, y: 353 + 40 * 4, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BG", x: 337, y: 353 + 40 * 4, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CG", x: 543, y: 353 + 40 * 4, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DG", x: 748, y: 353 + 40 * 4, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AF", x: 132, y: 353 + 40 * 5, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BF", x: 337, y: 353 + 40 * 5, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CF", x: 543, y: 353 + 40 * 5, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DF", x: 748, y: 353 + 40 * 5, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AE", x: 132, y: 353 + 40 * 6, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BE", x: 337, y: 353 + 40 * 6, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CE", x: 543, y: 353 + 40 * 6, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DE", x: 748, y: 353 + 40 * 6, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AD", x: 132, y: 353 + 40 * 7, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BD", x: 337, y: 353 + 40 * 7, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CD", x: 543, y: 353 + 40 * 7, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DD", x: 748, y: 353 + 40 * 7, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AC", x: 132, y: 353 + 40 * 8, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BC", x: 337, y: 353 + 40 * 8, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CC", x: 543, y: 353 + 40 * 8, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DC", x: 748, y: 353 + 40 * 8, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AB", x: 132, y: 353 + 40 * 9, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BB", x: 337, y: 353 + 40 * 9, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CB_1", x: 543, y: 353 + 40 * 9, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DB", x: 748, y: 353 + 40 * 9, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "AA", x: 132, y: 353 + 40 * 10, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "BA", x: 337, y: 353 + 40 * 10, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CA_1", x: 543, y: 353 + 40 * 10, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "DA", x: 748, y: 353 + 40 * 10, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "CA_2", x: 543, y: 740 + 40 + 7, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "CB_2", x: 543, y: 740 + 40 + 37, cols: 12, rows: 6, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        // { prefix: "Q", x: 305, y: 740 + 40 + 7, cols: 4, rows: 1, slotW: 7, slotH: 48, border: 0, color: "#FFFF00" },
        // { prefix: "Q", x: 721, y: 740 + 40 + 7, cols: 4, rows: 1, slotW: 10, slotH: 48, border: 0, color: "#FFFF00" },

        { prefix: "1", x: 271, y: 740 + 40 + 3, cols: 1, rows: 17, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "2", x: 214, y: 740 + 40 + 3, cols: 1, rows: 19, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "3", x: 168, y: 740 + 40 + 3, cols: 1, rows: 21, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "4", x: 129, y: 740 + 40 + 3, cols: 1, rows: 23, slotW: 14, slotH: 3, border: 0, color: "#93C47D" },

        { prefix: "EA", x: 449, y: 740 + 40 + 7, cols: 6, rows: 6, slotW: 11, slotH: 3, border: 0, color: "#93C47D" },
        { prefix: "EA", x: 493, y: 805, cols: 2, rows: 6, slotW: 11, slotH: 3, border: 0, color: "#93C47D", startIndex: 37 },

    ]
};
