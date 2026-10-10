import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path

DB = Path(__file__).with_name('grocery_store.db')

class GroceryApp:
    def __init__(self, root):
        self.root = root
        root.title('Grocery Store Management System')
        root.geometry('1050x690')
        self.db = sqlite3.connect(DB)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price>=0), stock INTEGER NOT NULL CHECK(stock>=0));
            CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, total REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id), product_id INTEGER NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL, price REAL NOT NULL);
        ''')
        self.cart = {}
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True, padx=12, pady=12)
        self.products_tab = ttk.Frame(self.tabs)
        self.billing_tab = ttk.Frame(self.tabs)
        self.sales_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.products_tab, text='Products & Inventory')
        self.tabs.add(self.billing_tab, text='Billing')
        self.tabs.add(self.sales_tab, text='Sales & Dashboard')
        self.build_products()
        self.build_billing()
        self.build_sales()
        self.refresh_all()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def build_products(self):
        form = ttk.LabelFrame(self.products_tab, text='Product Details', padding=12)
        form.pack(fill='x', padx=10, pady=10)
        self.fields = {}
        for i, (label, key) in enumerate([('Name','name'), ('Category','category'), ('Price (₹)','price'), ('Stock','stock')]):
            ttk.Label(form, text=label).grid(row=0, column=i, padx=6)
            entry = ttk.Entry(form, width=23)
            entry.grid(row=1, column=i, padx=6, pady=5)
            self.fields[key] = entry
        ttk.Button(form, text='Add Product', command=self.add_product).grid(row=2, column=0, pady=10)
        ttk.Button(form, text='Update Selected', command=self.update_product).grid(row=2, column=1)
        ttk.Button(form, text='Delete Selected', command=self.delete_product).grid(row=2, column=2)
        ttk.Button(form, text='Clear', command=self.clear_fields).grid(row=2, column=3)
        searchbar = ttk.Frame(self.products_tab)
        searchbar.pack(fill='x', padx=10)
        ttk.Label(searchbar, text='Search:').pack(side='left')
        self.search = ttk.Entry(searchbar)
        self.search.pack(side='left', fill='x', expand=True, padx=8)
        self.search.bind('<KeyRelease>', lambda e: self.refresh_products())
        columns = ('id','name','category','price','stock')
        self.product_tree = ttk.Treeview(self.products_tab, columns=columns, show='headings', height=17)
        for key, title, width in [('id','ID',65),('name','Product',260),('category','Category',190),('price','Price (₹)',130),('stock','Stock',100)]:
            self.product_tree.heading(key, text=title)
            self.product_tree.column(key, width=width)
        self.product_tree.pack(fill='both', expand=True, padx=10, pady=10)
        self.product_tree.bind('<<TreeviewSelect>>', self.select_product)
        self.product_tree.tag_configure('low', background='#fff0ce')

    def build_billing(self):
        top = ttk.LabelFrame(self.billing_tab, text='Add Item to Cart', padding=12)
        top.pack(fill='x', padx=10, pady=10)
        ttk.Label(top, text='Product:').grid(row=0, column=0, padx=5)
        self.product_choice = ttk.Combobox(top, state='readonly', width=55)
        self.product_choice.grid(row=0, column=1, padx=5)
        ttk.Label(top, text='Quantity:').grid(row=0, column=2, padx=5)
        self.quantity = tk.StringVar(value='1')
        ttk.Entry(top, textvariable=self.quantity, width=9).grid(row=0, column=3, padx=5)
        ttk.Button(top, text='Add to Cart', command=self.add_to_cart).grid(row=0, column=4, padx=5)
        columns = ('product','quantity','price','subtotal')
        self.cart_tree = ttk.Treeview(self.billing_tab, columns=columns, show='headings', height=15)
        for col, title in zip(columns, ['Product','Quantity','Unit Price (₹)','Subtotal (₹)']):
            self.cart_tree.heading(col, text=title)
            self.cart_tree.column(col, width=210)
        self.cart_tree.pack(fill='both', expand=True, padx=10, pady=10)
        bottom = ttk.Frame(self.billing_tab)
        bottom.pack(fill='x', padx=10, pady=10)
        self.total_label = ttk.Label(bottom, text='Total: ₹0.00', font=('Arial', 18, 'bold'))
        self.total_label.pack(side='left', padx=10)
        ttk.Button(bottom, text='Checkout & Save Bill', command=self.checkout).pack(side='right', padx=6)
        ttk.Button(bottom, text='Clear Cart', command=self.clear_cart).pack(side='right', padx=6)
        ttk.Button(bottom, text='Remove Selected', command=self.remove_cart_item).pack(side='right', padx=6)

    def build_sales(self):
        self.stats = ttk.Label(self.sales_tab, font=('Arial', 13), padding=15)
        self.stats.pack(fill='x')
        self.sales_tree = ttk.Treeview(self.sales_tab, columns=('id','date','total'), show='headings', height=13)
        for col, title in [('id','Bill Number'),('date','Date & Time'),('total','Amount (₹)')]:
            self.sales_tree.heading(col, text=title)
            self.sales_tree.column(col, width=240)
        self.sales_tree.pack(fill='both', expand=True, padx=10, pady=10)
        ttk.Button(self.sales_tab, text='View Selected Receipt', command=self.view_receipt).pack(pady=8)

    def parse_fields(self):
        name = self.fields['name'].get().strip()
        category = self.fields['category'].get().strip()
        if not name or not category:
            raise ValueError('Name and category are required.')
        price = float(self.fields['price'].get())
        stock = int(self.fields['stock'].get())
        if price < 0 or stock < 0 or price != price or price == float('inf'):
            raise ValueError('Price and stock must be nonnegative finite numbers.')
        return name, category, round(price,2), stock

    def selected_id(self):
        selected = self.product_tree.selection()
        if not selected:
            raise ValueError('Select a product first.')
        return int(selected[0])

    def add_product(self):
        try:
            data = self.parse_fields()
            with self.db:
                self.db.execute('INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)',data)
            self.clear_fields()
            self.refresh_all()
        except (ValueError,sqlite3.Error) as e:
            messagebox.showerror('Error',str(e))

    def update_product(self):
        try:
            pid = self.selected_id()
            data = self.parse_fields()
            with self.db:
                self.db.execute('UPDATE products SET name=?,category=?,price=?,stock=? WHERE id=?',(*data,pid))
            self.refresh_all()
        except (ValueError,sqlite3.Error) as e:
            messagebox.showerror('Error',str(e))

    def delete_product(self):
        try:
            pid = self.selected_id()
            if messagebox.askyesno('Confirm','Delete selected product?'):
                with self.db:
                    self.db.execute('DELETE FROM products WHERE id=?',(pid,))
                self.cart.pop(pid,None)
                self.refresh_all()
        except (ValueError,sqlite3.Error) as e:
            messagebox.showerror('Error',str(e))

    def clear_fields(self):
        for entry in self.fields.values():
            entry.delete(0,'end')

    def select_product(self, event=None):
        try:
            pid = self.selected_id()
        except ValueError:
            return
        row = self.db.execute('SELECT name,category,price,stock FROM products WHERE id=?',(pid,)).fetchone()
        if row:
            self.clear_fields()
            for key, value in zip(('name','category','price','stock'),row):
                self.fields[key].insert(0,str(value))

    def refresh_products(self):
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        term = '%' + self.search.get().strip() + '%'
        rows = self.db.execute('SELECT id,name,category,price,stock FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY name',(term,term))
        for pid,name,category,price,stock in rows:
            self.product_tree.insert('', 'end', iid=str(pid), values=(pid,name,category,f'{price:.2f}',stock), tags=('low',) if stock <= 5 else ())

    def refresh_choices(self):
        rows = self.db.execute('SELECT id,name,price,stock FROM products ORDER BY name').fetchall()
        self.choice_map = {f'{pid} | {name} | ₹{price:.2f} | Stock: {stock}':pid for pid,name,price,stock in rows}
        self.product_choice['values'] = list(self.choice_map)
        if self.product_choice.get() not in self.choice_map:
            self.product_choice.set('')

    def add_to_cart(self):
        try:
            pid = self.choice_map.get(self.product_choice.get())
            if pid is None:
                raise ValueError('Choose a product.')
            qty = int(self.quantity.get())
            if qty <= 0:
                raise ValueError('Quantity must be greater than zero.')
            row = self.db.execute('SELECT name,price,stock FROM products WHERE id=?',(pid,)).fetchone()
            if not row:
                raise ValueError('Product no longer exists.')
            name,price,stock = row
            existing = self.cart.get(pid,{}).get('qty',0)
            if existing + qty > stock:
                raise ValueError(f'Only {stock} units in stock ({existing} already in cart).')
            self.cart[pid] = {'name':name,'price':price,'qty':existing+qty}
            self.refresh_cart()
        except ValueError as e:
            messagebox.showerror('Error',str(e))

    def refresh_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        total = 0
        for pid,item in self.cart.items():
            subtotal = round(item['price']*item['qty'],2)
            total += subtotal
            self.cart_tree.insert('', 'end', iid=str(pid), values=(item['name'],item['qty'],f"{item['price']:.2f}",f'{subtotal:.2f}'))
        self.total_label.config(text=f'Total: ₹{total:.2f}')

    def remove_cart_item(self):
        for pid in self.cart_tree.selection():
            self.cart.pop(int(pid),None)
        self.refresh_cart()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart()

    def checkout(self):
        if not self.cart:
            messagebox.showwarning('Empty cart','Add products to the cart first.')
            return
        try:
            with self.db:
                total = 0
                items = []
                for pid,item in self.cart.items():
                    row = self.db.execute('SELECT name,price,stock FROM products WHERE id=?',(pid,)).fetchone()
                    if not row or row[2] < item['qty']:
                        raise ValueError(f"Insufficient stock for {item['name']}.")
                    name,price,stock = row
                    items.append((pid,name,item['qty'],price))
                    total += round(item['qty']*price,2)
                cursor = self.db.execute('INSERT INTO sales(created_at,total) VALUES(?,?)',(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),round(total,2)))
                sale_id = cursor.lastrowid
                for pid,name,qty,price in items:
                    self.db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid))
                    self.db.execute('INSERT INTO sale_items(sale_id,product_id,name,quantity,price) VALUES(?,?,?,?,?)',(sale_id,pid,name,qty,price))
            self.clear_cart()
            self.refresh_all()
            messagebox.showinfo('Sale Complete',f'Bill #{sale_id} saved. Total: ₹{total:.2f}')
            self.show_receipt(sale_id)
        except (ValueError,sqlite3.Error) as e:
            messagebox.showerror('Checkout failed',str(e))

    def refresh_sales(self):
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        for sid,date,total in self.db.execute('SELECT id,created_at,total FROM sales ORDER BY id DESC'):
            self.sales_tree.insert('', 'end', iid=str(sid),values=(sid,date,f'{total:.2f}'))
        products,units,value = self.db.execute('SELECT COUNT(*),COALESCE(SUM(stock),0),COALESCE(SUM(price*stock),0) FROM products').fetchone()
        count,revenue = self.db.execute('SELECT COUNT(*),COALESCE(SUM(total),0) FROM sales').fetchone()
        self.stats.config(text=f'Products: {products}     Units in Stock: {units}     Inventory Value: ₹{value:.2f}\nTotal Bills: {count}     Total Sales: ₹{revenue:.2f}')

    def view_receipt(self):
        selected = self.sales_tree.selection()
        if selected:
            self.show_receipt(int(selected[0]))
        else:
            messagebox.showwarning('Select bill','Select a sale first.')

    def show_receipt(self, sid):
        sale = self.db.execute('SELECT created_at,total FROM sales WHERE id=?',(sid,)).fetchone()
        if not sale:
            return
        items = self.db.execute('SELECT name,quantity,price FROM sale_items WHERE sale_id=?',(sid,)).fetchall()
        receipt = [f'GROCERY STORE RECEIPT',f'Bill No: {sid}',f'Date: {sale[0]}','-'*47]
        for name,qty,price in items:
            receipt.append(f'{name[:24]:24} {qty:>3} x {price:>7.2f} = {qty*price:>9.2f}')
        receipt.extend(['-'*47,f'TOTAL: ₹{sale[1]:.2f}','Thank you for shopping!'])
        window = tk.Toplevel(self.root)
        window.title(f'Receipt #{sid}')
        window.geometry('590x440')
        text = tk.Text(window,font=('Courier New',11),wrap='none')
        text.pack(fill='both',expand=True,padx=12,pady=12)
        text.insert('1.0','\n'.join(receipt))
        text.config(state='disabled')

    def refresh_all(self):
        self.refresh_products()
        self.refresh_choices()
        self.refresh_sales()
        self.refresh_cart()

    def close(self):
        self.db.close()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    GroceryApp(root)
    root.mainloop()
