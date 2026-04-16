# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, nowdate
from erpnext.stock.utils import get_latest_stock_qty
from erpnext.controllers.item_variant import create_variant, generate_keyed_value_combinations, get_variant


@frappe.whitelist()
def get_variants_data(template_item, company=None, warehouse=None, filter_attribute=None, filter_attribute_value=None):
	"""Fetch all variants of a template item with prices and stock quantities"""
	
	if not template_item:
		frappe.throw(_("Template Item is required"))
	
	# Check if item has variants
	template_doc = frappe.get_doc("Item", template_item)
	if not template_doc.has_variants:
		frappe.throw(_("Item {0} does not have variants").format(template_item))
	
	# Build filters for variants
	variant_filters = {"variant_of": template_item}
	
	# If filtering by attribute, get variants with that attribute value
	if filter_attribute and filter_attribute_value:
		variant_codes = frappe.db.sql("""
			SELECT DISTINCT iva.parent as item_code
			FROM `tabItem Variant Attribute` iva
			INNER JOIN `tabItem` i ON i.name = iva.parent
			WHERE i.variant_of = %s
			AND iva.attribute = %s
			AND iva.attribute_value = %s
		""", (template_item, filter_attribute, filter_attribute_value), as_list=True)
		variant_codes = [v[0] for v in variant_codes]
		if variant_codes:
			variant_filters["name"] = ["in", variant_codes]
		else:
			# No variants match, return empty result
			return {
				"template_item": template_item,
				"template_name": template_doc.item_name,
				"price_lists": [],
				"warehouses": [],
				"variants": []
			}
	
	# Get all variants
	variants = frappe.get_all(
		"Item",
		fields=["name", "item_code", "item_name", "disabled", "stock_uom"],
		filters=variant_filters,
		order_by="item_code"
	)
	
	# Get variant attributes
	variant_attributes_map = {}
	for variant in variants:
		attributes = frappe.get_all(
			"Item Variant Attribute",
			fields=["attribute", "attribute_value"],
			filters={"parent": variant.name},
			order_by="idx"
		)
		variant_attributes_map[variant.name] = attributes
	
	# Get all enabled price lists
	price_lists = frappe.get_all(
		"Price List",
		fields=["name", "currency", "buying", "selling"],
		filters={"enabled": 1},
		order_by="name"
	)
	
	# Get warehouses for stock calculation
	warehouses = []
	if warehouse:
		# If specific warehouse is selected, only show that one (prioritize warehouse filter)
		warehouses = [warehouse]
	elif company:
		warehouses = frappe.get_all(
			"Warehouse",
			fields=["name"],
			filters={"company": company, "is_group": 0},
			order_by="name",
			limit=10  # Limit to top 10 warehouses
		)
		warehouses = [w.name for w in warehouses]
	
	# Get prices for each variant
	variants_data = []
	for variant in variants:
		variant_data = {
			"item_code": variant.item_code,
			"item_name": variant.item_name,
			"disabled": variant.disabled,
			"stock_uom": variant.stock_uom,
			"attributes": variant_attributes_map.get(variant.name, []),
			"prices": {},
			"stock_qty": 0,
			"stock_by_warehouse": {},
			"valuation_rate": 0
		}
		
		# Get prices for each price list
		for price_list in price_lists:
			price = frappe.db.get_value(
				"Item Price",
				{
					"item_code": variant.item_code,
					"price_list": price_list.name,
					"uom": variant.stock_uom,
					"currency": price_list.currency
				},
				["price_list_rate", "name"],
				as_dict=True
			)
			
			if price:
				variant_data["prices"][price_list.name] = {
					"rate": price.price_list_rate,
					"name": price.name
				}
		
		# Get stock quantities
		if warehouse:
			# Single warehouse
			variant_data["stock_qty"] = get_latest_stock_qty(variant.item_code, warehouse) or 0
			variant_data["stock_by_warehouse"][warehouse] = variant_data["stock_qty"]
		elif warehouses:
			# Multiple warehouses
			total_qty = 0
			for wh in warehouses:
				qty = get_latest_stock_qty(variant.item_code, wh) or 0
				variant_data["stock_by_warehouse"][wh] = qty
				total_qty += qty
			variant_data["stock_qty"] = total_qty
		else:
			# No warehouse filter, get total stock
			variant_data["stock_qty"] = get_latest_stock_qty(variant.item_code) or 0
		
		# Get valuation rate
		if warehouse:
			valuation_rate = frappe.db.get_value(
				"Bin",
				{"item_code": variant.item_code, "warehouse": warehouse},
				"valuation_rate"
			)
			if not valuation_rate:
				valuation_rate = frappe.db.get_value("Item", variant.item_code, "valuation_rate")
		else:
			valuation_rate = frappe.db.get_value("Item", variant.item_code, "valuation_rate")
		
		variant_data["valuation_rate"] = flt(valuation_rate) or 0
		
		variants_data.append(variant_data)
	
	return {
		"template_item": template_item,
		"template_name": template_doc.item_name,
		"price_lists": price_lists,
		"warehouses": warehouses,
		"variants": variants_data
	}


def _set_variant_item_price(variant_code, price_list, rate, currency=None, uom=None):
	"""Update or create Item Price without committing."""

	if not variant_code or not price_list or rate is None:
		frappe.throw(_("Variant Code, Price List, and Rate are required"))

	pl_doc = frappe.get_doc("Price List", price_list)
	if not pl_doc.enabled:
		frappe.throw(_("Price List {0} is not enabled").format(price_list))

	currency = currency or pl_doc.currency

	if not uom:
		uom = frappe.db.get_value("Item", variant_code, "stock_uom")

	existing_price = frappe.db.get_value(
		"Item Price",
		{
			"item_code": variant_code,
			"price_list": price_list,
			"uom": uom,
			"currency": currency,
		},
	)

	if existing_price:
		frappe.db.set_value("Item Price", existing_price, "price_list_rate", flt(rate))
	else:
		price_doc = frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": variant_code,
				"price_list": price_list,
				"price_list_rate": flt(rate),
				"currency": currency,
				"uom": uom,
			}
		)
		price_doc.insert()


@frappe.whitelist()
def update_variant_price(variant_code, price_list, rate, currency=None, uom=None):
	"""Update or create price for a variant"""

	_set_variant_item_price(variant_code, price_list, rate, currency=currency, uom=uom)
	frappe.db.commit()

	return {"success": True}


@frappe.whitelist()
def bulk_update_prices(variants_data):
	"""Bulk update prices for multiple variants"""
	
	if isinstance(variants_data, str):
		import json
		variants_data = json.loads(variants_data)
	
	updated = 0
	errors = []
	
	for variant_code, prices in variants_data.items():
		for price_list, rate in prices.items():
			try:
				update_variant_price(variant_code, price_list, rate)
				updated += 1
			except Exception as e:
				errors.append({
					"variant": variant_code,
					"price_list": price_list,
					"error": str(e)
				})
	
	return {
		"updated": updated,
		"errors": errors
	}


@frappe.whitelist()
def get_stock_balance(variant_code, warehouse=None, company=None):
	"""Get stock balance for a variant"""
	
	if not variant_code:
		frappe.throw(_("Variant Code is required"))
	
	if warehouse:
		return get_latest_stock_qty(variant_code, warehouse) or 0
	elif company:
		warehouses = frappe.get_all(
			"Warehouse",
			fields=["name"],
			filters={"company": company}
		)
		total_qty = 0
		for wh in warehouses:
			total_qty += get_latest_stock_qty(variant_code, wh.name) or 0
		return flt(total_qty, 2)
	else:
		return get_latest_stock_qty(variant_code) or 0


@frappe.whitelist()
def create_variant_from_manager(template_item, attributes):
	"""Create a new variant from the variant manager page"""
	
	if isinstance(attributes, str):
		import json
		attributes = json.loads(attributes)
	
	if not template_item:
		frappe.throw(_("Template Item is required"))
	
	if not attributes:
		frappe.throw(_("Attributes are required"))
	
	# Check if variant already exists
	# Build filters to check for existing variant
	variant_filters = {"variant_of": template_item}
	
	# Check each attribute
	for attr_name, attr_value in attributes.items():
		# Get variant codes that have this attribute value
		existing_variants = frappe.db.sql("""
			SELECT DISTINCT iva.parent as item_code
			FROM `tabItem Variant Attribute` iva
			INNER JOIN `tabItem` i ON i.name = iva.parent
			WHERE i.variant_of = %s
			AND iva.attribute = %s
			AND iva.attribute_value = %s
		""", (template_item, attr_name, attr_value), as_list=True)
		
		if existing_variants:
			variant_codes = [v[0] for v in existing_variants]
			# Check if any of these variants have all the required attributes
			for variant_code in variant_codes:
				variant_attrs = frappe.get_all(
					"Item Variant Attribute",
					fields=["attribute", "attribute_value"],
					filters={"parent": variant_code}
				)
				variant_attr_dict = {attr.attribute: attr.attribute_value for attr in variant_attrs}
				
				# Check if all attributes match
				if all(variant_attr_dict.get(k) == v for k, v in attributes.items()):
					existing_variant = frappe.get_doc("Item", variant_code)
					frappe.throw(_("Variant with these attributes already exists: {0}").format(
						frappe.utils.get_link_to_form("Item", existing_variant.name)
					))
	
	# Use the existing create_variant function
	try:
		variant = create_variant(template_item, attributes)
		variant.insert()
		frappe.db.commit()
	except frappe.exceptions.DuplicateEntryError as e:
		frappe.db.rollback()
		# Try to find the existing variant
		existing_variants = frappe.get_all(
			"Item",
			fields=["name", "item_code"],
			filters={"variant_of": template_item}
		)
		
		# Check which variant has matching attributes
		for existing in existing_variants:
			variant_attrs = frappe.get_all(
				"Item Variant Attribute",
				fields=["attribute", "attribute_value"],
				filters={"parent": existing.name}
			)
			variant_attr_dict = {attr.attribute: attr.attribute_value for attr in variant_attrs}
			
			if all(variant_attr_dict.get(k) == v for k, v in attributes.items()):
				frappe.throw(_("Variant with these attributes already exists: {0}").format(
					frappe.utils.get_link_to_form("Item", existing.name)
				))
		
		# If we can't find it, throw a generic error
		frappe.throw(_("A variant with this item code already exists. Please check if the variant was already created."))
	
	return {
		"success": True,
		"variant_code": variant.item_code,
		"variant_name": variant.name
	}


MAX_MISSING_VARIANT_COMBINATIONS = 500


def _numeric_attribute_values(from_range, to_range, increment):
	increment = flt(increment)
	if increment <= 0:
		frappe.throw(_("Increment must be greater than zero for numeric variant attributes"))
	values = []
	current = flt(from_range)
	end = flt(to_range)
	# guard against huge ranges
	max_steps = 10000
	steps = 0
	while current <= end + 1e-9 and steps < max_steps:
		values.append(current)
		current = flt(current + increment)
		steps += 1
	if steps >= max_steps:
		frappe.throw(
			_("Numeric attribute range produces too many steps. Reduce the range or increase the increment.")
		)
	return values


@frappe.whitelist()
def get_missing_variant_combinations(template_item):
	"""Return attribute dicts for combinations that do not yet exist as Item variants."""

	if not template_item:
		frappe.throw(_("Template Item is required"))

	template_doc = frappe.get_doc("Item", template_item)
	if not template_doc.has_variants:
		frappe.throw(_("Item {0} does not have variants").format(template_item))
	if template_doc.variant_based_on != "Item Attribute":
		frappe.throw(_("Missing variants is only available when variant based on is Item Attribute"))

	value_map = {}
	for row in template_doc.attributes:
		if row.numeric_values:
			values = _numeric_attribute_values(row.from_range, row.to_range, row.increment)
		else:
			values = frappe.get_all(
				"Item Attribute Value",
				pluck="attribute_value",
				filters={"parent": row.attribute},
				order_by="idx",
			)
			values = [cstr(v) for v in values]
		if not values:
			frappe.throw(_("No values defined for attribute {0}").format(row.attribute))
		value_map[row.attribute] = values

	total = 1
	for vals in value_map.values():
		total *= len(vals)

	if total > MAX_MISSING_VARIANT_COMBINATIONS:
		frappe.throw(
			_(
				"There are {0} possible combinations. This tool can check at most {1}. "
				"Reduce attribute values or ranges before using Missing Variants."
			).format(total, MAX_MISSING_VARIANT_COMBINATIONS)
		)

	missing = []
	for combo in generate_keyed_value_combinations(value_map):
		if not get_variant(template_item, args=combo):
			# JSON-safe for the client (floats stay as numbers)
			missing.append({k: (flt(v) if isinstance(v, (int, float)) else cstr(v)) for k, v in combo.items()})

	return missing


@frappe.whitelist()
def create_missing_variants_batch(
	template_item, combinations, valuation_rate, standard_selling_rate, price_list=None
):
	"""Create variants for the given attribute combinations and set valuation + Standard Selling price."""

	if isinstance(combinations, str):
		combinations = json.loads(combinations)

	if not template_item:
		frappe.throw(_("Template Item is required"))
	if not combinations:
		frappe.throw(_("Select at least one variant to create"))
	if valuation_rate is None or valuation_rate == "":
		frappe.throw(_("Valuation Rate is required"))
	if standard_selling_rate is None or standard_selling_rate == "":
		frappe.throw(_("Standard Selling Rate is required"))

	if not price_list:
		price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"

	valuation_rate = flt(valuation_rate)
	standard_selling_rate = flt(standard_selling_rate)

	template_doc = frappe.get_doc("Item", template_item)
	if not template_doc.has_variants:
		frappe.throw(_("Item {0} does not have variants").format(template_item))

	required_attrs = [row.attribute for row in template_doc.attributes]

	created = []
	errors = []

	for attrs in combinations:
		if not isinstance(attrs, dict):
			errors.append({"attributes": attrs, "error": _("Invalid combination payload")})
			continue
		try:
			for attr in required_attrs:
				if attr not in attrs:
					frappe.throw(_("Missing value for attribute {0}").format(attr))
			if get_variant(template_item, args=attrs):
				errors.append({"attributes": attrs, "error": _("Variant already exists")})
				continue
			variant = create_variant(template_item, attrs)
			variant.insert()
			frappe.db.set_value("Item", variant.item_code, "valuation_rate", valuation_rate)
			_set_variant_item_price(variant.item_code, price_list, standard_selling_rate)
			frappe.db.commit()
			created.append(variant.item_code)
		except Exception as e:
			frappe.db.rollback()
			errors.append({"attributes": attrs, "error": cstr(e)})

	return {"created": created, "errors": errors, "price_list": price_list}


@frappe.whitelist()
def get_template_attributes(template_item):
	"""Get available attributes for a template item"""
	
	if not template_item:
		frappe.throw(_("Template Item is required"))
	
	template_doc = frappe.get_doc("Item", template_item)
	
	if not template_doc.has_variants:
		frappe.throw(_("Item {0} does not have variants").format(template_item))
	
	attributes = []
	for attr in template_doc.attributes:
		attr_doc = frappe.get_doc("Item Attribute", attr.attribute)
		values = frappe.get_all(
			"Item Attribute Value",
			fields=["attribute_value"],
			filters={"parent": attr.attribute},
			order_by="idx"
		)
		
		attributes.append({
			"attribute": attr.attribute,
			"attribute_name": attr_doc.attribute_name if hasattr(attr_doc, 'attribute_name') else attr.attribute,
			"values": [v.attribute_value for v in values],
			"numeric_values": attr_doc.numeric_values if hasattr(attr_doc, 'numeric_values') else 0
		})
	
	return attributes


@frappe.whitelist()
def set_price_by_attribute(template_item, attribute, attribute_value, price_list, rate, currency=None, uom=None):
	"""Set price for all variants containing a specific attribute value"""
	
	if not template_item or not attribute or not attribute_value or not price_list or rate is None:
		frappe.throw(_("Template Item, Attribute, Attribute Value, Price List, and Rate are required"))
	
	# Get all variants with this attribute value
	variants = frappe.db.sql("""
		SELECT DISTINCT iva.parent as item_code
		FROM `tabItem Variant Attribute` iva
		INNER JOIN `tabItem` i ON i.name = iva.parent
		WHERE i.variant_of = %s
		AND iva.attribute = %s
		AND iva.attribute_value = %s
	""", (template_item, attribute, attribute_value), as_dict=True)
	
	if not variants:
		frappe.msgprint(_("No variants found with attribute {0} = {1}").format(attribute, attribute_value))
		return {"updated": 0, "variants": []}
	
	# Get price list details
	pl_doc = frappe.get_doc("Price List", price_list)
	if not pl_doc.enabled:
		frappe.throw(_("Price List {0} is not enabled").format(price_list))
	
	currency = currency or pl_doc.currency
	updated = 0
	updated_variants = []
	
	for variant in variants:
		try:
			# Get item UOM if not provided
			if not uom:
				uom = frappe.db.get_value("Item", variant.item_code, "stock_uom")
			
			# Check if price exists
			existing_price = frappe.db.get_value(
				"Item Price",
				{
					"item_code": variant.item_code,
					"price_list": price_list,
					"uom": uom,
					"currency": currency
				}
			)
			
			if existing_price:
				frappe.db.set_value("Item Price", existing_price, "price_list_rate", flt(rate))
			else:
				price_doc = frappe.get_doc({
					"doctype": "Item Price",
					"item_code": variant.item_code,
					"price_list": price_list,
					"price_list_rate": flt(rate),
					"currency": currency,
					"uom": uom
				})
				price_doc.insert()
			
			updated += 1
			updated_variants.append(variant.item_code)
		except Exception as e:
			frappe.log_error(f"Error updating price for {variant.item_code}: {str(e)}")
	
	frappe.db.commit()
	frappe.msgprint(_("Updated price for {0} variant(s)").format(updated))
	
	return {
		"updated": updated,
		"variants": updated_variants
	}


@frappe.whitelist()
def get_valuation_rate(variant_code, company=None, warehouse=None):
	"""Get valuation rate for a variant"""
	
	if not variant_code:
		frappe.throw(_("Variant Code is required"))
	
	# Try to get from Bin first
	if warehouse:
		valuation_rate = frappe.db.get_value(
			"Bin",
			{"item_code": variant_code, "warehouse": warehouse},
			"valuation_rate"
		)
		if valuation_rate:
			return flt(valuation_rate)
	
	# Get from Item
	valuation_rate = frappe.db.get_value("Item", variant_code, "valuation_rate")
	if valuation_rate:
		return flt(valuation_rate)
	
	# Try standard_rate
	standard_rate = frappe.db.get_value("Item", variant_code, "standard_rate")
	if standard_rate:
		return flt(standard_rate)
	
	return 0.0


@frappe.whitelist()
def set_valuation_rate(variant_code, valuation_rate, company=None, warehouse=None):
	"""Set valuation rate for a variant"""
	
	if not variant_code or valuation_rate is None:
		frappe.throw(_("Variant Code and Valuation Rate are required"))
	
	# Update Item valuation_rate
	frappe.db.set_value("Item", variant_code, "valuation_rate", flt(valuation_rate))
	
	# If warehouse is specified, also update Bin
	if warehouse:
		bin_name = frappe.db.get_value("Bin", {"item_code": variant_code, "warehouse": warehouse})
		if bin_name:
			frappe.db.set_value("Bin", bin_name, "valuation_rate", flt(valuation_rate))
	
	frappe.db.commit()
	frappe.msgprint(_("Valuation rate updated for {0}").format(variant_code))
	
	return {"success": True}


@frappe.whitelist()
def bulk_set_valuation_rate(template_item, valuation_rates):
	"""Bulk set valuation rates for multiple variants"""
	
	if isinstance(valuation_rates, str):
		import json
		valuation_rates = json.loads(valuation_rates)
	
	if not template_item or not valuation_rates:
		frappe.throw(_("Template Item and Valuation Rates are required"))
	
	updated = 0
	errors = []
	
	for variant_code, rate in valuation_rates.items():
		try:
			frappe.db.set_value("Item", variant_code, "valuation_rate", flt(rate))
			updated += 1
		except Exception as e:
			errors.append({
				"variant": variant_code,
				"error": str(e)
			})
	
	frappe.db.commit()
	
	return {
		"updated": updated,
		"errors": errors
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_template_items_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	"""Custom query to get only template items (not variants)"""
	
	# Handle filters - pos_next override expects dict, but we need to handle both
	if isinstance(filters, str):
		import json
		filters = json.loads(filters)
	
	# Convert list filters to dict if needed
	if isinstance(filters, list):
		filters_dict = {}
		for f in filters:
			if len(f) >= 3:
				filters_dict[f[0]] = f[2] if len(f) == 3 else [f[1], f[2]]
	else:
		filters_dict = filters or {}
	
	# Build conditions for template items
	conditions = [
		"variant_of IS NULL",
		"has_variants = 1",
		"disabled = 0"
	]
	values = []
	
	# Add search condition
	if txt:
		conditions.append("(name LIKE %s OR item_name LIKE %s)")
		values.extend([f"%{txt}%", f"%{txt}%"])
	
	# Handle company filter from pos_next if present
	if filters_dict and isinstance(filters_dict, dict):
		company = filters_dict.get("company")
		if company:
			conditions.append("(custom_company = %s OR custom_company IS NULL OR custom_company = '')")
			values.append(company)
	
	query = f"""
		SELECT name, item_name, item_group
		FROM `tabItem`
		WHERE {' AND '.join(conditions)}
		ORDER BY
			CASE WHEN name LIKE %s THEN 0 ELSE 1 END,
			item_name
		LIMIT %s, %s
	"""
	
	values.extend([f"{txt}%", start, page_len])
	
	return frappe.db.sql(query, values, as_dict=as_dict)


@frappe.whitelist()
def update_stock_qty(variant_code, warehouse, qty, company=None):
	"""Update stock quantity for a variant by creating a Stock Reconciliation"""
	
	if not variant_code or not warehouse or qty is None:
		frappe.throw(_("Variant Code, Warehouse, and Quantity are required"))
	
	# Validate that the variant exists
	if not frappe.db.exists("Item", variant_code):
		frappe.throw(_("Item {0} does not exist").format(variant_code))
	
	# Validate that the warehouse exists
	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist").format(warehouse))
	
	# Get current stock
	current_qty = get_latest_stock_qty(variant_code, warehouse) or 0
	
	# Check if there's actually a change
	if abs(flt(qty) - flt(current_qty)) < 0.0001:
		# No change needed
		return {"success": True, "message": _("Stock quantity unchanged")}
	
	# Get company from warehouse if not provided
	if not company:
		company = frappe.db.get_value("Warehouse", warehouse, "company")
		if not company:
			frappe.throw(_("Company not found for warehouse {0}").format(warehouse))
	
	# Use Stock Reconciliation instead of Stock Entry - clearer and designed for this purpose
	from frappe.utils import nowdate, nowtime
	
	# Create Stock Reconciliation
	stock_reconciliation = frappe.new_doc("Stock Reconciliation")
	stock_reconciliation.purpose = "Stock Reconciliation"
	stock_reconciliation.posting_date = nowdate()
	stock_reconciliation.posting_time = nowtime()
	stock_reconciliation.company = company
	stock_reconciliation.set_warehouse = warehouse
	
	# Get expense account and cost center
	expense_account = frappe.get_cached_value("Company", company, "stock_adjustment_account")
	if expense_account:
		stock_reconciliation.expense_account = expense_account
	
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	if cost_center:
		stock_reconciliation.cost_center = cost_center
	
	# Get current valuation rate
	valuation_rate = frappe.db.get_value("Bin", {"item_code": variant_code, "warehouse": warehouse}, "valuation_rate")
	if not valuation_rate:
		valuation_rate = frappe.db.get_value("Item", variant_code, "valuation_rate") or 0
	
	# Add item to reconciliation
	stock_reconciliation.append("items", {
		"item_code": variant_code,
		"warehouse": warehouse,
		"qty": flt(qty),
		"valuation_rate": flt(valuation_rate)
	})
	
	# Save and submit
	stock_reconciliation.insert()
	stock_reconciliation.submit()
	frappe.db.commit()
	
	return {
		"success": True,
		"stock_reconciliation": stock_reconciliation.name,
		"message": _("Stock reconciled to {0}").format(qty)
	}


@frappe.whitelist()
def create_stock_entry(variant_code, warehouse, qty, company=None):
	"""Create a Stock Entry for adding or removing stock"""
	
	if not variant_code or not warehouse or qty is None:
		frappe.throw(_("Variant Code, Warehouse, and Quantity are required"))
	
	# Validate that the variant exists
	if not frappe.db.exists("Item", variant_code):
		frappe.throw(_("Item {0} does not exist").format(variant_code))
	
	# Validate that the warehouse exists
	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist").format(warehouse))
	
	# Get company from warehouse if not provided
	if not company:
		company = frappe.db.get_value("Warehouse", warehouse, "company")
		if not company:
			frappe.throw(_("Company not found for warehouse {0}").format(warehouse))
	
	from frappe.utils import nowdate, nowtime
	
	# Determine stock entry type based on quantity
	if flt(qty) > 0:
		stock_entry_type = "Material Receipt"
		t_warehouse = warehouse
		s_warehouse = None
		qty_to_use = flt(qty)
	else:
		stock_entry_type = "Material Issue"
		t_warehouse = None
		s_warehouse = warehouse
		qty_to_use = abs(flt(qty))
	
	# Create Stock Entry
	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = stock_entry_type
	stock_entry.posting_date = nowdate()
	stock_entry.posting_time = nowtime()
	stock_entry.company = company
	
	# Get default expense account and cost center
	expense_account = frappe.get_cached_value("Company", company, "stock_adjustment_account")
	if expense_account:
		stock_entry.expense_account = expense_account
	
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	if cost_center:
		stock_entry.cost_center = cost_center
	
	# Get valuation rate
	valuation_rate = frappe.db.get_value("Bin", {"item_code": variant_code, "warehouse": warehouse}, "valuation_rate")
	if not valuation_rate:
		valuation_rate = frappe.db.get_value("Item", variant_code, "valuation_rate") or 0
	
	# Add item row
	item_row = stock_entry.append("items", {
		"item_code": variant_code,
		"qty": qty_to_use,
		"uom": frappe.db.get_value("Item", variant_code, "stock_uom"),
		"valuation_rate": flt(valuation_rate)
	})
	
	if t_warehouse:
		item_row.t_warehouse = t_warehouse
	if s_warehouse:
		item_row.s_warehouse = s_warehouse
	
	# Save and submit (same as Stock Reconciliation)
	stock_entry.insert()
	stock_entry.submit()
	frappe.db.commit()
	
	return {
		"success": True,
		"stock_entry": stock_entry.name,
		"message": _("Stock Entry {0} created and submitted").format(stock_entry.name)
	}


@frappe.whitelist()
def bulk_set_prices(template_item, price_list, rate, attribute=None, attribute_value=None):
	"""Bulk set prices for all variants or variants matching attribute"""
	
	if not template_item or not price_list or rate is None:
		frappe.throw(_("Template Item, Price List, and Rate are required"))
	
	# Get price list details
	pl_doc = frappe.get_doc("Price List", price_list)
	if not pl_doc.enabled:
		frappe.throw(_("Price List {0} is not enabled").format(price_list))
	
	currency = pl_doc.currency
	
	# Get variants to update
	if attribute and attribute_value:
		# Filter by attribute
		variants = frappe.db.sql("""
			SELECT DISTINCT iva.parent as item_code
			FROM `tabItem Variant Attribute` iva
			INNER JOIN `tabItem` i ON i.name = iva.parent
			WHERE i.variant_of = %s
			AND iva.attribute = %s
			AND iva.attribute_value = %s
		""", (template_item, attribute, attribute_value), as_dict=True)
	else:
		# All variants
		variants = frappe.get_all(
			"Item",
			fields=["name as item_code"],
			filters={"variant_of": template_item}
		)
	
	if not variants:
		frappe.msgprint(_("No variants found"))
		return {"updated": 0, "variants": []}
	
	updated = 0
	updated_variants = []
	
	for variant in variants:
		try:
			# Get item UOM
			uom = frappe.db.get_value("Item", variant.item_code, "stock_uom")
			
			# Check if price exists
			existing_price = frappe.db.get_value(
				"Item Price",
				{
					"item_code": variant.item_code,
					"price_list": price_list,
					"uom": uom,
					"currency": currency
				}
			)
			
			if existing_price:
				frappe.db.set_value("Item Price", existing_price, "price_list_rate", flt(rate))
			else:
				price_doc = frappe.get_doc({
					"doctype": "Item Price",
					"item_code": variant.item_code,
					"price_list": price_list,
					"price_list_rate": flt(rate),
					"currency": currency,
					"uom": uom
				})
				price_doc.insert()
			
			updated += 1
			updated_variants.append(variant.item_code)
		except Exception as e:
			frappe.log_error(f"Error updating price for {variant.item_code}: {str(e)}")
	
	frappe.db.commit()
	frappe.msgprint(_("Updated price for {0} variant(s)").format(updated))
	
	return {
		"updated": updated,
		"variants": updated_variants
	}


@frappe.whitelist()
def bulk_set_valuation_rates(template_item, valuation_rate, attribute=None, attribute_value=None):
	"""Bulk set valuation rates for all variants or variants matching attribute"""
	
	if not template_item or valuation_rate is None:
		frappe.throw(_("Template Item and Valuation Rate are required"))
	
	# Get variants to update
	if attribute and attribute_value:
		# Filter by attribute
		variants = frappe.db.sql("""
			SELECT DISTINCT iva.parent as item_code
			FROM `tabItem Variant Attribute` iva
			INNER JOIN `tabItem` i ON i.name = iva.parent
			WHERE i.variant_of = %s
			AND iva.attribute = %s
			AND iva.attribute_value = %s
		""", (template_item, attribute, attribute_value), as_dict=True)
	else:
		# All variants
		variants = frappe.get_all(
			"Item",
			fields=["name as item_code"],
			filters={"variant_of": template_item}
		)
	
	if not variants:
		frappe.msgprint(_("No variants found"))
		return {"updated": 0, "variants": []}
	
	updated = 0
	updated_variants = []
	
	for variant in variants:
		try:
			# Update Item valuation_rate
			frappe.db.set_value("Item", variant.item_code, "valuation_rate", flt(valuation_rate))
			updated += 1
			updated_variants.append(variant.item_code)
		except Exception as e:
			frappe.log_error(f"Error updating valuation rate for {variant.item_code}: {str(e)}")
	
	frappe.db.commit()
	frappe.msgprint(_("Updated valuation rate for {0} variant(s)").format(updated))
	
	return {
		"updated": updated,
		"variants": updated_variants
	}
