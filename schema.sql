DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS offer;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  userType INTEGER NOT NULL,
  password TEXT NOT NULL,
  shopping_list JSON
);

CREATE TABLE offer (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  price FLOAT NOT NULL, 
  offername TEXT NOT NULL,
  image TEXT NOT NULL
);



