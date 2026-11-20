% ======================================================
% INFORMATION SYSTEM "BUYING A MOBILE PHONE"
% Student: Novitsky Alexander
% ======================================================

% ---------- DATABASE (FACTS) ----------
% phone(Model, Brand, Year, Color, RAM, ROM, Screen, Price, OS).

phone('iPhone 14', 'Apple', 2022, 'black', 6, 128, 6.1, 1200, 'iOS').
phone('iPhone 14 Pro', 'Apple', 2022, 'purple', 8, 256, 6.1, 1500, 'iOS').
phone('iPhone 15', 'Apple', 2023, 'pink', 8, 128, 6.2, 1400, 'iOS').
phone('Galaxy S23', 'Samsung', 2023, 'green', 8, 256, 6.6, 1100, 'Android').
phone('Galaxy S24', 'Samsung', 2024, 'grey', 12, 512, 6.7, 1400, 'Android').
phone('Galaxy A54', 'Samsung', 2023, 'white', 6, 128, 6.4, 450, 'Android').
phone('Xiaomi 13 Pro', 'Xiaomi', 2023, 'black', 12, 256, 6.7, 900, 'Android').
phone('Xiaomi Redmi Note 12', 'Xiaomi', 2022, 'blue', 4, 128, 6.5, 300, 'Android').
phone('Xiaomi Poco F5', 'Xiaomi', 2023, 'white', 8, 256, 6.6, 500, 'Android').
phone('Honor 90', 'Honor', 2023, 'green', 8, 256, 6.7, 550, 'Android').
phone('Honor X8', 'Honor', 2022, 'black', 6, 128, 6.5, 250, 'Android').
phone('Google Pixel 7', 'Google', 2022, 'grey', 8, 128, 6.3, 800, 'Android').
phone('Google Pixel 8', 'Google', 2023, 'black', 8, 256, 6.2, 950, 'Android').
phone('Nothing Phone 2', 'Nothing', 2023, 'white', 12, 256, 6.7, 850, 'Android').
phone('iPhone 13', 'Apple', 2021, 'blue', 4, 128, 6.1, 900, 'iOS').

% ---------- RULE 1: SEARCH BY BRAND ----------
find_by_brand(Brand, Models) :-
    findall(Model, phone(Model, Brand, _, _, _, _, _, _, _), Models).

% ---------- RULE 2: SEARCH CHEAPER THAN PRICE ----------
find_cheaper_than(MaxPrice, Models) :-
    findall(Model, (phone(Model, _, _, _, _, _, _, Price, _), Price =< MaxPrice), Models).

% ---------- RULE 3: SEARCH BY RAM ----------
find_by_ram(RAM, Models) :-
    findall(Model, phone(Model, _, _, _, RAM, _, _, _, _), Models).

% ---------- RULE 4: SEARCH BY YEAR ----------
find_by_year(Year, Models) :-
    findall(Model, phone(Model, _, Year, _, _, _, _, _, _), Models).

% ---------- RULE 5: SEARCH BY COLOR ----------
find_by_color(Color, Models) :-
    findall(Model, phone(Model, _, _, Color, _, _, _, _, _), Models).

% ---------- RULE 6: SEARCH BY ROM ----------
find_by_rom(ROM, Models) :-
    findall(Model, phone(Model, _, _, _, _, ROM, _, _, _), Models).

% ---------- RULE 7: SEARCH BY OS ----------
find_by_os(OS, Models) :-
    findall(Model, phone(Model, _, _, _, _, _, _, _, OS), Models).

% ---------- COMPLEX QUERY 1: MOST EXPENSIVE PHONE ----------
most_expensive(Model, Price) :-
    findall(Price1, phone(_, _, _, _, _, _, _, Price1, _), Prices),
    max_list(Prices, Price),
    phone(Model, _, _, _, _, _, _, Price, _).

% ---------- COMPLEX QUERY 2: BRAND PHONES ABOVE PRICE ----------
brand_above_price(Brand, MinPrice, Models) :-
    findall(Model, (phone(Model, Brand, _, _, _, _, _, Price, _), Price >= MinPrice), Models).

% ---------- COMPLEX QUERY 3: PHONES WITH ROM AT LEAST ----------
rom_at_least(MinROM, Models) :-
    findall(Model, (phone(Model, _, _, _, _, ROM, _, _, _), ROM >= MinROM), Models).

% ---------- HELPER: MAX OF LIST ----------
max_list([X], X).
max_list([H|T], Max) :-
    max_list(T, Max1),
    Max is max(H, Max1).

% ---------- PRINT LIST ----------
print_list([]).
print_list([H|T]) :-
    write(' - '), write(H), nl,
    print_list(T).

% ---------- MAIN MENU ----------
start :-
    nl, nl,
    write('============================================='), nl,
    write('   INFORMATION SYSTEM'), nl,
    write('   "BUYING A MOBILE PHONE"'), nl,
    write('============================================='), nl, nl,
    write('1. Search by brand'), nl,
    write('2. Search cheaper than price'), nl,
    write('3. Search by RAM'), nl,
    write('4. Search by year'), nl,
    write('5. Search by color'), nl,
    write('6. Search by ROM'), nl,
    write('7. Search by OS'), nl,
    write('8. Most expensive phone'), nl,
    write('9. Brand phones above price'), nl,
    write('10. Phones with ROM at least'), nl,
    write('0. Exit'), nl, nl,
    write('Choose option: '),
    read(Option),
    handle_option(Option).

% ---------- HANDLE CHOICE ----------
handle_option(0) :-
    write('Program finished. Goodbye!'), nl.

handle_option(1) :-
    write('Enter brand (Apple, Samsung, Xiaomi, Honor, Google, Nothing): '),
    read(Brand),
    find_by_brand(Brand, Models),
    write('Phones of brand '), write(Brand), write(':'), nl,
    print_list(Models),
    start.

handle_option(2) :-
    write('Enter max price (USD): '),
    read(MaxPrice),
    find_cheaper_than(MaxPrice, Models),
    write('Phones cheaper than '), write(MaxPrice), write(' USD:'), nl,
    print_list(Models),
    start.

handle_option(3) :-
    write('Enter RAM (4,6,8,12): '),
    read(RAM),
    find_by_ram(RAM, Models),
    write('Phones with RAM '), write(RAM), write(' GB:'), nl,
    print_list(Models),
    start.

handle_option(4) :-
    write('Enter year (2021-2024): '),
    read(Year),
    find_by_year(Year, Models),
    write('Phones of year '), write(Year), write(':'), nl,
    print_list(Models),
    start.

handle_option(5) :-
    write('Enter color (black, white, blue, green, pink, purple, grey): '),
    read(Color),
    find_by_color(Color, Models),
    write('Phones of color '), write(Color), write(':'), nl,
    print_list(Models),
    start.

handle_option(6) :-
    write('Enter ROM (128,256,512): '),
    read(ROM),
    find_by_rom(ROM, Models),
    write('Phones with ROM '), write(ROM), write(' GB:'), nl,
    print_list(Models),
    start.

handle_option(7) :-
    write('Enter OS (iOS, Android): '),
    read(OS),
    find_by_os(OS, Models),
    write('Phones on '), write(OS), write(':'), nl,
    print_list(Models),
    start.

handle_option(8) :-
    most_expensive(Model, Price),
    write('Most expensive phone: '), write(Model), 
    write(' (price '), write(Price), write(' USD)'), nl,
    start.

handle_option(9) :-
    write('Enter brand: '),
    read(Brand),
    write('Enter min price (USD): '),
    read(MinPrice),
    brand_above_price(Brand, MinPrice, Models),
    write('Phones of '), write(Brand), write(' above '), write(MinPrice), write(' USD:'), nl,
    print_list(Models),
    start.

handle_option(10) :-
    write('Enter min ROM (128,256,512): '),
    read(MinROM),
    rom_at_least(MinROM, Models),
    write('Phones with ROM >= '), write(MinROM), write(' GB:'), nl,
    print_list(Models),
    start.

handle_option(_) :-
    write('Invalid choice.'), nl,
    start.