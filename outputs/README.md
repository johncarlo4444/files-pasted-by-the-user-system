# World Fast Food Express

ILAGAN, JOHN CARLO A. 
MANDIGMA, ZANCH
DIAZ, AXCEL JEFF
MONTIFAR, RANIEL
TAMAYO, SOPHIA LORRAINE
DIMAANO, CRISTEL
GENEROSO, GLEN

Offline Tkinter ordering and management app using a local MySQL server.

## Setup

1. Install Python 3.10 or newer and MySQL Community Server.
2. From this folder, install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Set `FASTFOOD_DB_HOST`, `FASTFOOD_DB_PORT`, `FASTFOOD_DB_USER`,
   `FASTFOOD_DB_PASSWORD`, and `FASTFOOD_DB_NAME` if the defaults in
   `config.py` do not match your local MySQL configuration. Set
   `FASTFOOD_RESTAURANT_NAME`, `FASTFOOD_BRANCH`, `FASTFOOD_ADDRESS`, and
   `FASTFOOD_CONTACT` to customize receipt details.
4. Initialize the schema and famous-food menu:

   ```powershell
   python database.py
   ```

   If a previous setup attempt stopped with a missing `users` or `payments`
   table, use the updated `database.py` and run this command again. The setup
   creates any missing tables and then seeds the starter data.

   The starter staff login is `admin` / `admin123`. Change that password from
   **Admin → Staff Users** after signing in.
If `admin` / `admin123` does not work on an existing database, reset the
local admin password from this folder:

```powershell
python reset_admin_password.py
```

The script prompts for a new password, reactivates the local `admin` account,
and leaves orders and menu data untouched. The schema seed does not overwrite
an existing admin password.

5. Start the desktop app:

   ```powershell
   python main.py
   ```

When the app starts, it applies additive schema upgrades to an existing
database before opening the kiosk. If MySQL is unavailable or the upgrade
cannot complete, the app shows the database error and a Retry button. You do
not need to rerun the full seed script just to add a newer table. If an older
database contains repeated products in the same category, startup consolidates
them under the newest product entry, keeps order history and recipe links, and
adds a unique key so the seed script cannot add those duplicates again.

Receipt text and PDF files are saved under `receipts/`. Product photos selected
in the admin menu are copied into `assets/menu/` and shown on kiosk cards. You
can also place photos there using the product-name filename, for example
`assets/menu/classic-double-cheeseburger.jpg`; supported formats are PNG, JPG,
JPEG, and WebP. MySQL must be running locally while the app is in use; orders
and reports are stored in that local database.
