-- Every query is named so run.py can load it. Dates are normalised with date()
-- because the source mixes plain dates and timestamps.

-- name: base
CREATE TEMP VIEW shipped AS
SELECT o.OrderID,
       o.ShipVia                                                        AS carrier,
       o.EmployeeID                                                     AS employee,
       o.ShipCountry                                                    AS country,
       substr(o.OrderDate, 6, 2)                                        AS month,
       CAST(strftime('%w', date(o.OrderDate)) AS INT)                   AS weekday,
       CAST(julianday(date(o.RequiredDate)) - julianday(date(o.OrderDate)) AS INT) AS lead_days,
       CAST(julianday(date(o.ShippedDate))  - julianday(date(o.OrderDate)) AS INT) AS ship_days,
       date(o.ShippedDate) > date(o.RequiredDate)                       AS late
FROM Orders o
WHERE o.ShippedDate IS NOT NULL;

-- name: quality
SELECT
 (SELECT COUNT(*) FROM Orders)                                                           AS orders,
 (SELECT COUNT(*) FROM "Order Details")                                                  AS order_lines,
 (SELECT COUNT(*) FROM Orders o LEFT JOIN Customers c USING(CustomerID) WHERE c.CustomerID IS NULL) AS orphan_customers,
 (SELECT COUNT(*) FROM "Order Details" d LEFT JOIN Orders o USING(OrderID) WHERE o.OrderID IS NULL) AS orphan_lines,
 (SELECT COUNT(*) FROM Orders WHERE date(ShippedDate)  < date(OrderDate))                AS shipped_before_ordered,
 (SELECT COUNT(*) FROM Orders WHERE date(RequiredDate) < date(OrderDate))                AS required_before_ordered,
 (SELECT COUNT(*) FROM Orders WHERE ShippedDate IS NULL)                                 AS not_yet_shipped,
 (SELECT COUNT(*) FROM Orders WHERE length(OrderDate) > 10 OR length(ShippedDate) > 10)  AS mixed_date_formats;

-- name: overall
SELECT COUNT(*) AS n, AVG(late) AS rate FROM shipped;

-- name: by_lead
SELECT lead_days, COUNT(*) AS n, AVG(late) AS rate FROM shipped GROUP BY lead_days ORDER BY lead_days;

-- name: dims
SELECT 'Carrier' AS dim, CAST(carrier AS TEXT) AS seg, COUNT(*) AS n, AVG(late) AS rate FROM shipped GROUP BY 2
UNION ALL SELECT 'Employee', CAST(employee AS TEXT), COUNT(*), AVG(late) FROM shipped GROUP BY 2
UNION ALL SELECT 'Month ordered', month, COUNT(*), AVG(late) FROM shipped GROUP BY 2
UNION ALL SELECT 'Weekday ordered', CAST(weekday AS TEXT), COUNT(*), AVG(late) FROM shipped GROUP BY 2
UNION ALL SELECT 'Ship-to country', country, COUNT(*), AVG(late) FROM shipped GROUP BY 2
UNION ALL SELECT 'Promised lead time',
  CASE WHEN lead_days <= 7 THEN '0-7 days' WHEN lead_days <= 14 THEN '8-14 days'
       WHEN lead_days <= 28 THEN '15-28 days' ELSE '29+ days' END, COUNT(*), AVG(late) FROM shipped GROUP BY 2;

-- name: ship_by_lead
SELECT CASE WHEN lead_days <= 7 THEN '0-7 days' WHEN lead_days <= 14 THEN '8-14 days'
            WHEN lead_days <= 28 THEN '15-28 days' ELSE '29+ days' END AS bucket,
       AVG(ship_days) AS avg_ship_days
FROM shipped GROUP BY 1;

-- name: ship_days
SELECT ship_days, COUNT(*) AS n FROM shipped GROUP BY ship_days ORDER BY ship_days;
