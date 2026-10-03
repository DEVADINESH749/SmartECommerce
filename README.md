# Smart E-Commerce Platform

A full-stack Smart E-Commerce Platform with a customer shopping interface, FastAPI backend, Django admin panel, MySQL database, Auth0 authentication, Stripe test payments, notifications, email notifications, analytics, and reports.

## Project Overview

The Smart E-Commerce Platform provides:

- Customer registration and login
- Google and Facebook login through Auth0
- Product browsing and product details
- Category, price, and popularity-based product filtering
- Shopping cart
- Order creation and order history
- Stripe test payment integration
- Order status management
- In-app notifications
- Email notifications
- Django admin panel
- User and role management
- Product management
- Order and payment management
- Analytics dashboard
- CSV and PDF reports
- Responsive customer frontend

## Technologies Used

### Frontend
- React
- Vite
- JavaScript
- CSS
- Stripe React
- Auth0 React SDK

### Backend
- FastAPI
- Python
- SQLAlchemy
- PyMySQL
- JWT Authentication

### Admin Panel
- Django
- Django Admin

### Database
- MySQL 8.0

### Authentication
- Local email/password authentication
- Auth0
- Google Login
- Facebook Login

### Payment
- Stripe Test Mode

### Reports
- CSV
- PDF
- ReportLab

## Project Architecture

```text
SmartECommerce
│
├── backend
│   ├── fastapi
│   │   ├── Authentication
│   │   ├── Products
│   │   ├── Cart
│   │   ├── Orders
│   │   ├── Payments
│   │   ├── Notifications
│   │   └── Email
│   │
│   └── django
│       ├── Admin Panel
│       ├── Analytics
│       └── Reports
│
├── frontend
│   └── React Application
│
├── postman
│   └── SmartECommerce.postman_collection.json
│
├── database
│   └── Local database backup
│
└── docs
    └── Project documentation