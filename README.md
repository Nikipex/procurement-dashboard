Procurement Dashboard

Internal Business Intelligence platform for procurement and inventory management in a gas equipment distribution company.

⸻

Overview

Procurement Dashboard is a production-oriented analytics system built to replace manual Excel workflows and provide real-time visibility into sales, inventory, purchasing and supplier performance.

The platform operates on real company data extracted directly from 1C PostgreSQL and serves as the foundation for procurement decision-making.

Current ecosystem:

1C PostgreSQL → Data Layer → Analytics Engine → Dashboard → Executive PDF Reports

⸻

Business Goals

The system helps procurement teams:

* Reduce manual reporting
* Monitor inventory levels
* Detect critical stock shortages
* Forecast purchasing needs
* Optimize supplier decisions
* Improve stock turnover
* Increase visibility across product categories

⸻

Core Features

Inventory Analytics

* Current stock monitoring
* Reserved stock tracking
* Available stock calculation
* Days of cover analysis
* Critical stock detection
* Warehouse-level visibility

Procurement Planning

* Demand forecasting
* Purchase recommendations
* Velocity classification
    * FAST
    * MEDIUM
    * SLOW
* Reorder calculations
* Procurement prioritization

Product Categories

* Gas boilers
* Water heaters
* Radiators
* Pumps
* Chimney systems
* Voltage stabilizers
* Accessories

Reporting

* Interactive HTML dashboard
* Executive PDF reports
* ABC analysis
* Gross profit analytics
* Product rankings
* Sales performance metrics

⸻

Data Sources

Primary source:

* 1C PostgreSQL (read-only)

Additional sources:

* Supplier price lists
* Historical sales datasets
* Inventory registers
* Procurement planning datasets

⸻

1C PostgreSQL Reverse Engineering

Key entities discovered during project development:

Documents

Sales documents:

public._document240

Sales lines:

public._document240_vt6039

Products

public._reference80

Warehouses

public._reference100

Inventory Registers

public._accumrgt9117

Used for real stock calculations.

⸻

South Warehouse

Main operational warehouse:

Name:

ЮЖНЫЙ склад

Warehouse ID:

83ee60f67771497111e9dbb16ec97a48

⸻

Architecture

1C PostgreSQL

↓

SQL Views

↓

Normalization Layer

↓

Analytics Services

↓

Dashboard / PDF Reports

⸻

Technology Stack

Backend

* Python 3.12+
* PostgreSQL
* SQLAlchemy
* Pandas

Analytics

* Plotly
* NumPy

Presentation

* Jinja2
* HTML Dashboard
* ReportLab
* WeasyPrint

Infrastructure

* Redis
* Docker
* Systemd

⸻

Reliability

Implemented reliability mechanisms:

* PostgreSQL integration
* Snapshot fallback catalog
* Redis caching
* Automated refresh jobs
* Last-known-good inventory snapshots

The platform can continue operating with cached inventory data even during temporary database outages.

⸻

Current Status

Production / Internal Commercial Use

Completed:

* Connected to real 1C PostgreSQL
* Reverse engineered key 1C structures
* Built SQL analytics layer
* Implemented inventory calculations
* Implemented procurement logic
* Implemented executive PDF reporting
* Implemented dashboard analytics

Used on real sales and inventory data.

⸻

Roadmap

* Supplier Intelligence
* Advanced Forecasting
* Automated Procurement Recommendations
* Expanded Supplier Analytics
* AI-assisted Procurement Insights

⸻

Project Type

Commercial Internal Tool

Built for a real gas equipment distribution company and used on production business data.
