-- Question: How are trips split by payment type? (one row per payment type)
SELECT 
	payment_type,
	CASE 
		WHEN payment_type = 0 THEN 'Flex Fare'
		WHEN payment_type = 1 THEN 'Credit card'
		WHEN payment_type = 2 THEN 'Cash'
		WHEN payment_type = 3 THEN 'No charge'
		WHEN payment_type = 4 THEN 'Dispute'
		WHEN payment_type = 5 THEN 'Unknown'
		WHEN payment_type = 6 THEN 'Voided trip'
		ELSE 'Other'
	END AS payment_label,
	COUNT(*) AS trip_count,
	ROUND((COUNT(*) * 100.0) / SUM(COUNT(*)) OVER (), 2) AS pct_of_trips
FROM clean.trips
GROUP BY payment_type
ORDER BY trip_count DESC;