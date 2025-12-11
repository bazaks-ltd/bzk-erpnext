frappe.pages["item-variant-manager"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Item Variant Manager"),
		single_column: true,
	});

	page.template_item = null;
	page.variants_data = null;
	page.price_lists = [];

	// Get template item from URL params or route options
	page.get_template_from_url = function() {
		// First check route options (for when navigating from Item form)
		if (frappe.route_options) {
			var template = frappe.route_options.template_item || frappe.route_options["template-item"];
			if (template) {
				frappe.route_options = null;
				return template;
			}
		}
		
		// Then check URL params (support both template_item and template-item)
		var urlParams = new URLSearchParams(window.location.search);
		var template_from_url = urlParams.get('template-item') || urlParams.get('template_item');
		
		// URL params might be JSON encoded, try to parse
		if (template_from_url) {
			try {
				var decoded = JSON.parse(template_from_url);
				if (typeof decoded === 'string') {
					return decoded;
				}
			} catch(e) {
				// Not JSON, use as is
			}
		}
		
		return template_from_url;
	};

	page.template_item = page.get_template_from_url();

	// Template item field - only show template items (not variants)
	page.template_field = page.add_field({
		fieldname: "template_item",
		label: __("Template Item"),
		fieldtype: "Link",
		options: "Item",
		reqd: 1,
		default: page.template_item,
		get_query: function() {
			// Use query method to handle filters properly with pos_next override
			return {
				query: "erpnext.item_variant_manager.api.item_variant_manager.get_template_items_query"
			};
		},
		change: function() {
			var new_template = page.template_field.get_value();
			if (new_template !== page.template_item) {
				page.template_item = new_template;
				// Update URL with template item
				page.update_url_with_template();
				// Load template attributes for filters
				if (page.template_item) {
					page.load_template_attributes_for_filter();
					page.load_variants();
				}
			}
		}
	});

	// Update URL with template item parameter
	page.update_url_with_template = function() {
		if (page.template_item) {
			frappe.route_options = {
				"template-item": page.template_item
			};
			// Update URL without reloading
			var url = "/app/item-variant-manager?template-item=" + encodeURIComponent(page.template_item);
			window.history.pushState({}, "", url);
		}
	};

	// Company field for stock calculation
	page.company_field = page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		default: frappe.defaults.get_default("company"),
		change: function() {
			// Update warehouse default when company changes
			var company = page.company_field.get_value();
			if (company) {
				// Try to get default warehouse from Stock Settings
				frappe.call({
					method: "frappe.client.get_value",
					args: {
						doctype: "Stock Settings",
						name: "Stock Settings",
						fieldname: "default_warehouse"
					},
					callback: function(r) {
						var default_warehouse = r.message && r.message.default_warehouse;
						// Check if warehouse belongs to the selected company
						if (default_warehouse) {
							frappe.call({
								method: "frappe.client.get_value",
								args: {
									doctype: "Warehouse",
									name: default_warehouse,
									fieldname: "company"
								},
								callback: function(r2) {
									if (r2.message && r2.message.company === company) {
										page.warehouse_field.set_value(default_warehouse);
									} else {
										// Clear warehouse if it doesn't belong to the new company
										page.warehouse_field.set_value("");
									}
									if (page.template_item) {
										page.load_variants();
									}
								}
							});
						} else {
							// No default warehouse, clear it
							page.warehouse_field.set_value("");
							if (page.template_item) {
								page.load_variants();
							}
						}
					}
				});
			} else {
				// No company selected, clear warehouse
				page.warehouse_field.set_value("");
				if (page.template_item) {
					page.load_variants();
				}
			}
		}
	});

	// Warehouse field (filter)
	page.warehouse_field = page.add_field({
		fieldname: "warehouse",
		label: __("Filter by Warehouse"),
		fieldtype: "Link",
		options: "Warehouse",
		get_query: function() {
			var company = page.company_field.get_value();
			if (company) {
				return {
					filters: {
						company: company,
						is_group: 0
					}
				};
			}
			return {
				filters: {
					is_group: 0
				}
			};
		},
		change: function() {
			if (page.template_item) {
				page.load_variants();
			}
		}
	});
	
	// Get default warehouse from Stock Settings and set it
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Stock Settings",
			name: "Stock Settings",
			fieldname: "default_warehouse"
		},
		callback: function(r) {
			if (r.message && r.message.default_warehouse) {
				page.warehouse_field.set_value(r.message.default_warehouse);
			}
		}
	});

	// Store template attributes for filters
	page.template_attributes_for_filter = [];

	// Attribute filter field
	page.attribute_filter_field = page.add_field({
		fieldname: "filter_attribute",
		label: __("Filter by Attribute"),
		fieldtype: "Select",
		options: "",
		change: function() {
			var selected_attr = page.attribute_filter_field.get_value();
			if (selected_attr) {
				var attr_obj = page.template_attributes_for_filter.find(function(a) {
					return (a.attribute_name || a.attribute) === selected_attr;
				});
				if (attr_obj) {
					var attr_values = attr_obj.values || [];
					// Update options directly
					page.attribute_value_filter_field.df.options = attr_values;
					page.attribute_value_filter_field.set_value('');
					
					// Update autocomplete immediately without refresh first
					var field = page.attribute_value_filter_field;
					var $input = field.$input || (field.control && field.control.$input) || (field.$wrapper && field.$wrapper.find('input'));
					
					if ($input && $input.length > 0) {
						var input = $input[0];
						var awesomplete_instance = null;
						
						// Find existing awesomplete
						if (field.awesomplete) {
							awesomplete_instance = field.awesomplete;
						} else if (field.control && field.control.awesomplete) {
							awesomplete_instance = field.control.awesomplete;
						} else if ($input.data('awesomplete')) {
							awesomplete_instance = $input.data('awesomplete');
						} else if (input.awesomplete) {
							awesomplete_instance = input.awesomplete;
						}
						
						// Update or create awesomplete
						if (awesomplete_instance) {
							awesomplete_instance.list = attr_values;
						} else if (typeof Awesomplete !== 'undefined') {
							awesomplete_instance = new Awesomplete(input, {
								minChars: 0,
								maxItems: 99,
								list: attr_values
							});
							if (field.control) {
								field.control.awesomplete = awesomplete_instance;
							} else {
								field.awesomplete = awesomplete_instance;
							}
							$input.data('awesomplete', awesomplete_instance);
						}
					}
					
					// Also refresh the field to ensure UI is updated
					page.attribute_value_filter_field.refresh();
					
					// Update autocomplete again after field is refreshed (in case it was recreated)
					setTimeout(function() {
						var field = page.attribute_value_filter_field;
						if (!field) return;
						
						// Try multiple approaches to update the autocomplete
						var updated = false;
						
						// Approach 1: Use set_data method if available (Frappe autocomplete control)
						if (field.set_data && typeof field.set_data === 'function') {
							field.set_data(attr_values);
							updated = true;
						}
						
						// Approach 2: Access through control property
						if (!updated && field.control && field.control.set_data && typeof field.control.set_data === 'function') {
							field.control.set_data(attr_values);
							updated = true;
						}
						
						// Approach 3: Manually update awesomplete
						if (!updated) {
							// Find the input element
							var $input = null;
							if (field.$input) {
								$input = field.$input;
							} else if (field.control && field.control.$input) {
								$input = field.control.$input;
							} else if (field.$wrapper) {
								$input = field.$wrapper.find('input[data-fieldname="filter_attribute_value"]');
								if (!$input || $input.length === 0) {
									$input = field.$wrapper.find('input');
								}
							}
							
							if ($input && $input.length > 0) {
								var input = $input[0];
								
								// Update existing awesomplete
								if (field.awesomplete) {
									field.awesomplete.list = attr_values;
									updated = true;
								} else if (field.control && field.control.awesomplete) {
									field.control.awesomplete.list = attr_values;
									updated = true;
								} else if ($input.data('awesomplete')) {
									$input.data('awesomplete').list = attr_values;
									updated = true;
								} else if (input.awesomplete) {
									input.awesomplete.list = attr_values;
									updated = true;
								} else if (typeof Awesomplete !== 'undefined' && attr_values.length > 0) {
									// Create new awesomplete instance
									var awesomplete = new Awesomplete(input, {
										minChars: 0,
										maxItems: 99,
										list: attr_values
									});
									if (field.control) {
										field.control.awesomplete = awesomplete;
									} else {
										field.awesomplete = awesomplete;
									}
									$input.data('awesomplete', awesomplete);
									updated = true;
								}
							}
						}
						
						// If still not updated, try one more time after a longer delay
						if (!updated) {
							setTimeout(function() {
								var field2 = page.attribute_value_filter_field;
								if (field2 && field2.control && field2.control.set_data) {
									field2.control.set_data(attr_values);
								} else if (field2 && field2.$wrapper) {
									var $input2 = field2.$wrapper.find('input');
									if ($input2 && $input2.length > 0 && typeof Awesomplete !== 'undefined') {
										var input2 = $input2[0];
										if (!input2.awesomplete && !$input2.data('awesomplete')) {
											var awesomplete2 = new Awesomplete(input2, {
												minChars: 0,
												maxItems: 99,
												list: attr_values
											});
											$input2.data('awesomplete', awesomplete2);
										} else {
											var awesomplete_instance = input2.awesomplete || $input2.data('awesomplete');
											if (awesomplete_instance) {
												awesomplete_instance.list = attr_values;
											}
										}
									}
								}
							}, 500);
						}
						
						// Trigger input event to show autocomplete when user focuses
						setTimeout(function() {
							var field3 = page.attribute_value_filter_field;
							if (field3) {
								var $input3 = field3.$input || (field3.control && field3.control.$input) || (field3.$wrapper && field3.$wrapper.find('input'));
								if ($input3 && $input3.length > 0) {
									// Store the values so they're available when user types
									$input3.data('autocomplete-values', attr_values);
								}
							}
						}, 100);
					}, 300);
				}
			} else {
				page.attribute_value_filter_field.df.options = [];
				page.attribute_value_filter_field.set_value('');
				page.attribute_value_filter_field.refresh();
				
				// Clear autocomplete
				setTimeout(function() {
					var field = page.attribute_value_filter_field;
					if (!field) return;
					
					var $input = field.$input || (field.$wrapper ? field.$wrapper.find('input') : null);
					if ($input && $input.length > 0) {
						var input = $input[0];
						if (field.awesomplete) {
							field.awesomplete.list = [];
						} else if ($input.data('awesomplete')) {
							$input.data('awesomplete').list = [];
						} else if (input.awesomplete) {
							input.awesomplete.list = [];
						}
					}
				}, 300);
			}
			if (page.template_item) {
				page.load_variants();
			}
		}
	});

	// Attribute value filter field
	page.attribute_value_filter_field = page.add_field({
		fieldname: "filter_attribute_value",
		label: __("Filter by Attribute Value"),
		fieldtype: "Autocomplete",
		options: [],
		change: function() {
			if (page.template_item) {
				page.load_variants();
			}
		}
	});

	// Create variant button
	page.add_button(__("Create New Variant"), function() {
		page.show_create_variant_dialog();
	}, { icon: "add", btn_class: "btn-primary" });

	// Bulk set prices button
	page.add_button(__("Bulk Set Prices"), function() {
		page.show_bulk_set_prices_dialog();
	}, { icon: "tag" });

	// Bulk set valuation rate button
	page.add_button(__("Bulk Set Valuation Rate"), function() {
		page.show_bulk_set_valuation_rate_dialog();
	}, { icon: "money" });

	// Refresh button
	page.add_button(__("Refresh"), function() {
		if (page.template_item) {
			page.load_variants();
		}
	}, { icon: "refresh" });

	// Main content area - full height
	page.content_area = $('<div class="variant-manager-content"></div>').appendTo(page.main);
	
	// Add CSS for full height layout
	$('<style>')
		.prop('type', 'text/css')
		.html(`
			.variant-manager-content {
				height: calc(100vh - 200px);
				overflow-y: auto;
			}
			.variant-list-container {
				height: 100%;
				overflow-y: auto;
			}
			.modal-dialog {
				z-index: 1050 !important;
			}
			.modal-backdrop {
				z-index: 1040 !important;
			}
		`)
		.appendTo('head');

	// Load template attributes for filter
	page.load_template_attributes_for_filter = function() {
		if (!page.template_item) return;
		
		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_template_attributes",
			args: {
				template_item: page.template_item
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					page.template_attributes_for_filter = r.message;
					var attribute_options = r.message.map(function(attr) {
						return attr.attribute_name || attr.attribute;
					}).join('\n');
					page.attribute_filter_field.df.options = attribute_options;
					page.attribute_filter_field.refresh();
					// Clear attribute value filter
					page.attribute_value_filter_field.df.options = [];
					page.attribute_value_filter_field.set_value('');
					page.attribute_value_filter_field.refresh();
					
					// Clear autocomplete list
					setTimeout(function() {
						var field = page.attribute_value_filter_field;
						if (field && field.awesomplete) {
							field.awesomplete.list = [];
						} else if (field && field.$input) {
							var $input = field.$input;
							if ($input.data('awesomplete')) {
								$input.data('awesomplete').list = [];
							}
						}
					}, 100);
				}
			}
		});
	};

	// Render variants function (defined before load_variants so it can be called)
	page.render_variants = function() {
		if (!page.variants_data || !page.variants_data.variants || page.variants_data.variants.length === 0) {
			page.content_area.html('<div class="text-center" style="padding: 40px; color: #6c757d;">' + __("No variants found.") + '</div>');
			return;
		}

		// Build HTML directly to avoid template rendering issues
		var warehouses = page.variants_data.warehouses || [];
		var warehouse_cols = warehouses.length > 0 ? warehouses.length : 1;
		var col_width = Math.floor(12 / (warehouse_cols + 6)); // 6 other columns
		
		var html = '<div class="variant-manager-header" style="padding: 12px 15px; background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;">';
		html += '<div class="row">';
		html += '<div class="col-sm-2 text-muted" style="margin-top: 8px;"><strong>' + __("Item Code") + '</strong></div>';
		html += '<div class="col-sm-2 text-muted" style="margin-top: 8px;"><strong>' + __("Attributes") + '</strong></div>';
		
		// Warehouse columns
		if (warehouses.length > 0) {
			warehouses.forEach(function(wh) {
				html += '<div class="col-sm-' + col_width + ' text-muted" style="margin-top: 8px;"><strong>' + frappe.utils.escape_html(wh) + '</strong></div>';
			});
		} else {
			html += '<div class="col-sm-1 text-muted" style="margin-top: 8px;"><strong>' + __("Total Stock") + '</strong></div>';
		}
		
		html += '<div class="col-sm-1 text-muted" style="margin-top: 8px;"><strong>' + __("Valuation Rate") + '</strong></div>';
		html += '<div class="col-sm-3 text-muted" style="margin-top: 8px;"><strong>' + __("Prices") + '</strong></div>';
		html += '<div class="col-sm-1 text-muted" style="margin-top: 8px;"><strong>' + __("Actions") + '</strong></div>';
		html += '</div></div>';
		html += '<div class="variant-list-container">';

		page.variants_data.variants.forEach(function(variant) {
			html += '<div class="variant-item dashboard-list-item" data-variant="' + frappe.utils.escape_html(variant.item_code) + '" style="padding: 10px 15px; border-bottom: 1px solid #e9ecef;">';
			html += '<div class="row">';
			
			// Item Code
			html += '<div class="col-sm-2" style="margin-top: 8px;">';
			html += '<a href="/app/item/' + frappe.utils.escape_html(variant.item_code) + '" target="_blank" class="variant-link">';
			html += '<strong>' + frappe.utils.escape_html(variant.item_code) + '</strong></a>';
			if (variant.disabled) {
				html += '<br><span class="badge badge-secondary">' + __("Disabled") + '</span>';
			}
			html += '</div>';
			
			// Attributes
			html += '<div class="col-sm-2" style="margin-top: 8px;">';
			if (variant.attributes && variant.attributes.length > 0) {
				variant.attributes.forEach(function(attr) {
					html += '<div><small class="text-muted">' + frappe.utils.escape_html(attr.attribute) + ':</small> ';
					html += '<strong>' + frappe.utils.escape_html(attr.attribute_value) + '</strong></div>';
				});
			}
			html += '</div>';
			
			// Stock Qty by Warehouse
			if (warehouses.length > 0) {
				warehouses.forEach(function(wh) {
					var stock_qty = variant.stock_by_warehouse && variant.stock_by_warehouse[wh] ? variant.stock_by_warehouse[wh] : 0;
					html += '<div class="col-sm-' + col_width + '" style="margin-top: 8px;">';
					html += '<div style="font-size: 9px; color: #666; margin-bottom: 2px;">Current: ' + stock_qty.toFixed(0) + '</div>';
					html += '<button class="btn btn-xs btn-primary manage-stock-btn" ';
					html += 'style="font-size: 10px; padding: 2px 8px;" ';
					html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '" ';
					html += 'data-warehouse="' + frappe.utils.escape_html(wh) + '" ';
					html += 'title="' + __("Manage Stock") + '">';
					html += '<i class="fa fa-edit"></i> ' + __("Manage") + '</button>';
					html += '</div>';
				});
			} else {
				html += '<div class="col-sm-1" style="margin-top: 8px;">';
				html += '<span class="stock-qty" data-variant="' + frappe.utils.escape_html(variant.item_code) + '">';
				html += (variant.stock_qty || 0).toFixed(2) + ' ' + (variant.stock_uom || '');
				html += '</span></div>';
			}
			
			// Valuation Rate
			html += '<div class="col-sm-1" style="margin-top: 8px;">';
			html += '<input type="number" class="form-control valuation-rate-input" ';
			html += 'style="display: inline-block; width: 100px;" ';
			html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '" ';
			html += 'value="' + (variant.valuation_rate || 0).toFixed(2) + '" placeholder="0.00" step="0.01" /> ';
			html += '<button class="btn btn-xs btn-primary save-valuation-btn" ';
			html += 'style="margin-left: 5px; display: none;" ';
			html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '">';
			html += __("Save") + '</button></div>';
			
			// Prices
			html += '<div class="col-sm-3 price-list-container" data-variant="' + frappe.utils.escape_html(variant.item_code) + '">';
			page.price_lists.forEach(function(price_list) {
				var price_data = variant.prices && variant.prices[price_list.name] ? variant.prices[price_list.name] : null;
				var price_rate = price_data ? price_data.rate : '';
				
				html += '<div class="price-item" style="margin-bottom: 5px;" data-price-list="' + frappe.utils.escape_html(price_list.name) + '">';
				html += '<small class="text-muted">' + frappe.utils.escape_html(price_list.name) + ':</small> ';
				html += '<input type="number" class="form-control price-input" ';
				html += 'style="display: inline-block; width: 120px; margin-left: 5px;" ';
				html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '" ';
				html += 'data-price-list="' + frappe.utils.escape_html(price_list.name) + '" ';
				html += 'data-currency="' + frappe.utils.escape_html(price_list.currency) + '" ';
				html += 'value="' + (price_rate || '') + '" placeholder="0.00" step="0.01" /> ';
				html += '<span class="currency-symbol">' + frappe.utils.escape_html(price_list.currency) + '</span> ';
				html += '<button class="btn btn-xs btn-primary save-price-btn" ';
				html += 'style="margin-left: 5px; display: none;" ';
				html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '" ';
				html += 'data-price-list="' + frappe.utils.escape_html(price_list.name) + '">';
				html += __("Save") + '</button></div>';
			});
			html += '</div>';
			
			// Actions
			html += '<div class="col-sm-1" style="margin-top: 8px;">';
			html += '<button class="btn btn-xs btn-secondary refresh-all-btn" ';
			html += 'data-variant="' + frappe.utils.escape_html(variant.item_code) + '" ';
			html += 'title="' + __("Refresh Stock & Valuation") + '">';
			html += '<i class="fa fa-refresh"></i></button></div>';
			
			html += '</div></div>';
		});
		
		html += '</div>';
		page.content_area.html(html);
		page.setup_event_handlers();
	};

	// Load variants function
	page.load_variants = function() {
		if (!page.template_item) {
			frappe.msgprint(__("Please select a template item"));
			return;
		}

		page.content_area.html('<div class="text-center" style="padding: 40px;"><i class="fa fa-spinner fa-spin fa-2x"></i><br><br>' + __("Loading variants...") + '</div>');

		// Get filter values
		var filter_attribute = page.attribute_filter_field.get_value();
		var filter_attribute_value = page.attribute_value_filter_field.get_value();
		var filter_attribute_obj = null;
		
		if (filter_attribute) {
			filter_attribute_obj = page.template_attributes_for_filter.find(function(a) {
				return (a.attribute_name || a.attribute) === filter_attribute;
			});
		}

		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_variants_data",
			args: {
				template_item: page.template_item,
				company: page.company_field ? page.company_field.get_value() : null,
				warehouse: page.warehouse_field ? page.warehouse_field.get_value() : null,
				filter_attribute: filter_attribute_obj ? filter_attribute_obj.attribute : null,
				filter_attribute_value: filter_attribute_value || null
			},
			callback: function(r) {
				if (r.message) {
					page.variants_data = r.message;
					page.price_lists = r.message.price_lists || [];
					page.render_variants();
				}
			},
			error: function(r) {
				frappe.msgprint(__("Error loading variants: {0}", [r.message || "Unknown error"]));
			}
		});
	};

	// Load variants if template is set
	if (page.template_item) {
		page.load_template_attributes_for_filter();
		page.load_variants();
	}

	// Initialize stock update tracking at page level
	page.stockUpdateInProgress = {};
	page.stockManagementDialogOpen = false;
	
	// Setup event handlers
	page.setup_event_handlers = function() {
		// Price input change handlers
		page.content_area.find('.price-input').on('input', function() {
			var $btn = $(this).siblings('.save-price-btn');
			$btn.show();
		});

		// Save price button
		page.content_area.on('click', '.save-price-btn', function() {
			var $btn = $(this);
			var variant_code = $btn.data('variant');
			var price_list = $btn.data('price-list');
			var $input = $btn.siblings('.price-input');
			var rate = parseFloat($input.val());

			if (isNaN(rate) || rate < 0) {
				frappe.msgprint(__("Please enter a valid price"));
				return;
			}

			$btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

			frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.update_variant_price",
				args: {
					variant_code: variant_code,
					price_list: price_list,
					rate: rate,
					currency: $input.data('currency'),
					uom: null
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						$btn.hide();
						frappe.show_alert({
							message: __("Price updated successfully"),
							indicator: 'green'
						}, 3);
					}
					$btn.prop('disabled', false).html(__("Save"));
				},
				error: function(r) {
					frappe.msgprint(__("Error updating price: {0}", [r.message || "Unknown error"]));
					$btn.prop('disabled', false).html(__("Save"));
				}
			});
		});

		// Manage stock button - opens dialog for stock correction or stock entry
		// Remove any existing handlers first to prevent duplicates
		page.content_area.off('click', '.manage-stock-btn');
		page.content_area.on('click', '.manage-stock-btn', function(e) {
			e.preventDefault();
			e.stopPropagation();
			e.stopImmediatePropagation();
			
			var $btn = $(this);
			
			// Prevent multiple clicks
			if ($btn.prop('disabled')) {
				return false;
			}
			
			var variant_code = $btn.data('variant');
			var warehouse = $btn.data('warehouse');
			
			// Prevent opening multiple dialogs
			if (page.stockManagementDialogOpen) {
				return false;
			}
			
			// Get current stock
			var current_qty = 0;
			var variant_data = page.variants_data.variants.find(v => v.item_code === variant_code);
			if (variant_data && variant_data.stock_by_warehouse) {
				current_qty = variant_data.stock_by_warehouse[warehouse] || 0;
			}
			
			// Show dialog to choose between Stock Reconciliation or Stock Entry
			page.show_stock_management_dialog(variant_code, warehouse, current_qty);
			
			return false;
		});

		// Refresh all button (stock and valuation)
		page.content_area.on('click', '.refresh-all-btn', function() {
			var $btn = $(this);
			var variant_code = $btn.data('variant');
			var $variantRow = $btn.closest('.variant-item');

			$btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

			// Refresh stock for all warehouses
			var warehouses = page.variants_data.warehouses || [];
			var stockPromises = [];
			
			warehouses.forEach(function(wh) {
				stockPromises.push(
					frappe.call({
						method: "erpnext.item_variant_manager.api.item_variant_manager.get_stock_balance",
						args: {
							variant_code: variant_code,
							warehouse: wh,
							company: page.company_field.get_value()
						}
					})
				);
			});

			// Refresh valuation rate
			var valuationPromise = frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.get_valuation_rate",
				args: {
					variant_code: variant_code,
					company: page.company_field.get_value(),
					warehouse: page.warehouse_field.get_value()
				}
			});

			Promise.all([...stockPromises, valuationPromise]).then(function(results) {
				var variant_data = page.variants_data.variants.find(v => v.item_code === variant_code);
				if (variant_data) {
					// Update stock by warehouse
					if (!variant_data.stock_by_warehouse) {
						variant_data.stock_by_warehouse = {};
					}
					var total = 0;
					warehouses.forEach(function(wh, idx) {
						if (results[idx] && results[idx].message !== undefined) {
							var qty = parseFloat(results[idx].message) || 0;
							variant_data.stock_by_warehouse[wh] = qty;
							total += qty;
							var $input = $variantRow.find('.stock-qty-input[data-warehouse="' + wh + '"]');
							if ($input.length) {
								$input.val(qty.toFixed(2));
							}
						}
					});
					variant_data.stock_qty = total;

					// Update valuation rate
					if (results[results.length - 1] && results[results.length - 1].message !== undefined) {
						var rate = parseFloat(results[results.length - 1].message) || 0;
						variant_data.valuation_rate = rate;
						var $valuationInput = $variantRow.find('.valuation-rate-input');
						if ($valuationInput.length) {
							$valuationInput.val(rate.toFixed(2));
						}
					}
				}
				$btn.prop('disabled', false).html('<i class="fa fa-refresh"></i>');
			}).catch(function(err) {
				frappe.msgprint(__("Error refreshing data: {0}", [err.message || "Unknown error"]));
				$btn.prop('disabled', false).html('<i class="fa fa-refresh"></i>');
			});
		});

		// Valuation rate input change handlers
		page.content_area.find('.valuation-rate-input').on('input', function() {
			var $btn = $(this).siblings('.save-valuation-btn');
			$btn.show();
		});

		// Save valuation rate button
		page.content_area.on('click', '.save-valuation-btn', function() {
			var $btn = $(this);
			var variant_code = $btn.data('variant');
			var $input = $btn.siblings('.valuation-rate-input');
			var rate = parseFloat($input.val());

			if (isNaN(rate) || rate < 0) {
				frappe.msgprint(__("Please enter a valid valuation rate"));
				return;
			}

			$btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

			frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.set_valuation_rate",
				args: {
					variant_code: variant_code,
					valuation_rate: rate,
					company: page.company_field.get_value(),
					warehouse: page.warehouse_field.get_value()
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						$btn.hide();
						var variant_data = page.variants_data.variants.find(v => v.item_code === variant_code);
						if (variant_data) {
							variant_data.valuation_rate = rate;
						}
						frappe.show_alert({
							message: __("Valuation rate updated successfully"),
							indicator: 'green'
						}, 3);
					}
					$btn.prop('disabled', false).html(__("Save"));
				},
				error: function(r) {
					frappe.msgprint(__("Error updating valuation rate: {0}", [r.message || "Unknown error"]));
					$btn.prop('disabled', false).html(__("Save"));
				}
			});
		});

	};

	// Show create variant dialog
	page.show_create_variant_dialog = function() {
		if (!page.template_item) {
			frappe.msgprint(__("Please select a template item first"));
			return;
		}

		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_template_attributes",
			args: {
				template_item: page.template_item
			},
			callback: function(r) {
				if (r.message) {
					page.show_attribute_selection_dialog(r.message);
				}
			},
			error: function(r) {
				frappe.msgprint(__("Error loading attributes: {0}", [r.message || "Unknown error"]));
			}
		});
	};

	// Show attribute selection dialog
	page.show_attribute_selection_dialog = function(attributes) {
		var fields = [];

		attributes.forEach(function(attr) {
			if (attr.numeric_values) {
				fields.push({
					fieldtype: 'Float',
					label: attr.attribute_name || attr.attribute,
					fieldname: attr.attribute,
					reqd: 1
				});
			} else {
				fields.push({
					fieldtype: 'Select',
					label: attr.attribute_name || attr.attribute,
					fieldname: attr.attribute,
					options: attr.values.join('\n'),
					reqd: 1
				});
			}
		});

		var d = new frappe.ui.Dialog({
			title: __("Create New Variant"),
			fields: fields,
			primary_action_label: __("Create"),
			primary_action: function(values) {
				d.hide();
				page.create_variant(values);
			}
		});

		d.show();
	};

	// Create variant
	page.create_variant = function(attributes) {
		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.create_variant_from_manager",
			args: {
				template_item: page.template_item,
				attributes: attributes
			},
			freeze: true,
			freeze_message: __("Creating variant..."),
			callback: function(r) {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Variant {0} created successfully", [r.message.variant_code]),
						indicator: 'green'
					}, 5);
					page.load_variants();
				}
			},
			error: function(r) {
				var error_msg = r.message || "Unknown error";
				if (typeof error_msg === 'string') {
					frappe.msgprint(__("Error creating variant: {0}", [error_msg]));
				} else if (error_msg.exc_type) {
					frappe.msgprint(__("Error creating variant: {0}", [error_msg.exc_message || error_msg.exc_type]));
				} else {
					frappe.msgprint(__("Error creating variant: {0}", [JSON.stringify(error_msg)]));
				}
			}
		});
	};

	// Show set price by attribute dialog
	page.show_set_price_by_attribute_dialog = function() {
		if (!page.template_item) {
			frappe.msgprint(__("Please select a template item first"));
			return;
		}

		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_template_attributes",
			args: {
				template_item: page.template_item
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					page.show_price_by_attribute_dialog(r.message);
				} else {
					frappe.msgprint(__("No attributes found for this template item"));
				}
			},
			error: function(r) {
				frappe.msgprint(__("Error loading attributes: {0}", [r.message || "Unknown error"]));
			}
		});
	};

	// Show price by attribute dialog
	page.show_price_by_attribute_dialog = function(attributes) {
		// Store attributes for later use
		page.template_attributes = attributes;
		
		var attribute_options = attributes.map(function(attr) {
			return attr.attribute_name || attr.attribute;
		}).join('\n');

		var fields = [
			{
				fieldtype: 'Select',
				label: __("Attribute"),
				fieldname: 'attribute',
				options: attribute_options,
				reqd: 1,
				change: function() {
					var selected_attr = d.get_value('attribute');
					var attr_obj = attributes.find(function(a) {
						return (a.attribute_name || a.attribute) === selected_attr;
					});
					if (attr_obj) {
						if (attr_obj.numeric_values) {
							d.set_df_property('attribute_value', 'fieldtype', 'Float');
							d.set_df_property('attribute_value', 'options', '');
						} else {
							d.set_df_property('attribute_value', 'fieldtype', 'Select');
							d.set_df_property('attribute_value', 'options', attr_obj.values.join('\n'));
						}
						d.refresh_field('attribute_value');
					}
				}
			},
			{
				fieldtype: 'Data',
				label: __("Attribute Value"),
				fieldname: 'attribute_value',
				reqd: 1
			},
			{
				fieldtype: 'Link',
				label: __("Price List"),
				fieldname: 'price_list',
				options: 'Price List',
				reqd: 1,
				get_query: function() {
					return {
						filters: {
							enabled: 1
						}
					};
				}
			},
			{
				fieldtype: 'Currency',
				label: __("Rate"),
				fieldname: 'rate',
				reqd: 1
			}
		];

		var d = new frappe.ui.Dialog({
			title: __("Set Price by Attribute"),
			fields: fields,
			primary_action_label: __("Set Price"),
			primary_action: function(values) {
				d.hide();
				page.set_price_by_attribute(values, attributes);
			}
		});

		d.show();
	};

	// Set price by attribute
	page.set_price_by_attribute = function(values, attributes) {
		// Find the actual attribute name from the display name
		var selected_attr_display = values.attribute;
		var attr_obj = attributes.find(function(a) {
			return (a.attribute_name || a.attribute) === selected_attr_display;
		});
		
		if (attr_obj) {
			frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.set_price_by_attribute",
				args: {
					template_item: page.template_item,
					attribute: attr_obj.attribute,
					attribute_value: values.attribute_value,
					price_list: values.price_list,
					rate: values.rate
				},
				freeze: true,
				freeze_message: __("Setting prices..."),
				callback: function(r) {
					if (r.message) {
						frappe.show_alert({
							message: __("Price updated for {0} variant(s)", [r.message.updated]),
							indicator: 'green'
						}, 5);
						page.load_variants();
					}
				},
				error: function(r) {
					frappe.msgprint(__("Error setting prices: {0}", [r.message || "Unknown error"]));
				}
			});
		} else {
			frappe.msgprint(__("Attribute not found"));
		}
	};

	// Show bulk set prices dialog
	page.show_bulk_set_prices_dialog = function() {
		if (!page.template_item) {
			frappe.msgprint(__("Please select a template item first"));
			return;
		}

		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_template_attributes",
			args: {
				template_item: page.template_item
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					page.show_bulk_prices_dialog(r.message);
				} else {
					// No attributes, show dialog without attribute filter
					page.show_bulk_prices_dialog([]);
				}
			},
			error: function(r) {
				// Show dialog without attributes if error
				page.show_bulk_prices_dialog([]);
			}
		});
	};

	// Show bulk prices dialog
	page.show_bulk_prices_dialog = function(attributes) {
		var fields = [];
		var current_attribute_values = [];
		var selected_attribute_obj = null;
		
		// Attribute field (optional) - from template item attributes
		if (attributes.length > 0) {
			var attribute_options = attributes.map(function(attr) {
				return attr.attribute_name || attr.attribute;
			}).join('\n');
			
			fields.push({
				fieldtype: 'Select',
				label: __("Attribute (Optional)"),
				fieldname: 'attribute',
				options: attribute_options,
				change: function() {
					var selected_attr = d.get_value('attribute');
					selected_attribute_obj = attributes.find(function(a) {
						return (a.attribute_name || a.attribute) === selected_attr;
					});
					if (selected_attribute_obj) {
						current_attribute_values = selected_attribute_obj.values || [];
						var attr_value_field = d.fields_dict.attribute_value;
						
						if (selected_attribute_obj.numeric_values) {
							// For numeric values, use Float field
							d.set_df_property('attribute_value', 'fieldtype', 'Float');
							d.set_df_property('attribute_value', 'options', '');
							d.set_value('attribute_value', '');
							d.refresh_field('attribute_value');
						} else {
							// Update options without refreshing to preserve autocomplete
							d.set_df_property('attribute_value', 'options', current_attribute_values);
							d.set_value('attribute_value', '');
							
							// Function to update autocomplete directly without refresh
							var update_autocomplete_direct = function() {
								var attr_value_field = d.fields_dict.attribute_value;
								if (!attr_value_field) return false;
								
								// Try set_data method first
								if (attr_value_field.set_data && typeof attr_value_field.set_data === 'function') {
									attr_value_field.set_data(current_attribute_values);
									return true;
								}
								
								if (attr_value_field.control && attr_value_field.control.set_data && typeof attr_value_field.control.set_data === 'function') {
									attr_value_field.control.set_data(current_attribute_values);
									return true;
								}
								
								// Find input element - try multiple ways
								var $input = attr_value_field.$input || 
									(attr_value_field.control && attr_value_field.control.$input) || 
									(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input[data-fieldname="attribute_value"]')) ||
									(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input')) ||
									d.$wrapper.find('input[data-fieldname="attribute_value"]');
								
								if ($input && $input.length > 0) {
									var input = $input[0];
									
									// Find existing awesomplete
									var awesomplete = attr_value_field.awesomplete ||
										(attr_value_field.control && attr_value_field.control.awesomplete) ||
										$input.data('awesomplete') ||
										input.awesomplete;
									
									if (awesomplete) {
										awesomplete.list = current_attribute_values;
										return true;
									} else if (typeof Awesomplete !== 'undefined' && current_attribute_values.length > 0) {
										// Create new awesomplete
										awesomplete = new Awesomplete(input, {
											minChars: 0,
											maxItems: 99,
											list: current_attribute_values
										});
										if (attr_value_field.control) {
											attr_value_field.control.awesomplete = awesomplete;
										} else {
											attr_value_field.awesomplete = awesomplete;
										}
										$input.data('awesomplete', awesomplete);
										return true;
									}
								}
								return false;
							};
							
							// Try to update immediately
							if (!update_autocomplete_direct()) {
								// If failed, refresh field and try again
								d.refresh_field('attribute_value');
								setTimeout(function() {
									update_autocomplete_direct();
								}, 400);
							}
							
							// Store update function on dialog
							d._update_attribute_autocomplete = update_autocomplete_direct;
						}
					}
				}
			});
			
			fields.push({
				fieldtype: 'Autocomplete',
				label: __("Attribute Value (Optional)"),
				fieldname: 'attribute_value',
				options: []
			});
		}
		
		fields.push({
			fieldtype: 'Link',
			label: __("Price List"),
			fieldname: 'price_list',
			options: 'Price List',
			reqd: 1,
			get_query: function() {
				return {
					filters: {
						enabled: 1
					}
				};
			}
		});
		
		fields.push({
			fieldtype: 'Currency',
			label: __("Price List Rate"),
			fieldname: 'rate',
			reqd: 1
		});

		var d = new frappe.ui.Dialog({
			title: __("Bulk Set Prices"),
			fields: fields,
			primary_action_label: __("Set Prices"),
			primary_action: function(values) {
				d.hide();
				page.bulk_set_prices(values, attributes);
			},
			onhide: function() {
				// Clean up when dialog is closed
				selected_attribute_obj = null;
				current_attribute_values = [];
			}
		});

		// Set default price list to Standard Selling
		frappe.db.get_value("Selling Settings", "Selling Settings", "selling_price_list", function(r) {
			var default_price_list = (r && r.selling_price_list) || "Standard Selling";
			if (d.fields_dict.price_list) {
				d.set_value('price_list', default_price_list);
			}
		});

		// Fix z-index to appear above buttons
		d.$wrapper.css('z-index', '1050');
		
		// Fix z-index to appear above buttons
		d.$wrapper.css('z-index', '1050');
		
		d.show();
		
		// After dialog is shown, set up autocomplete update mechanism
		setTimeout(function() {
			// Store reference to attributes for use in update function
			d._attribute_values_map = {};
			attributes.forEach(function(attr) {
				var key = attr.attribute_name || attr.attribute;
				d._attribute_values_map[key] = attr.values || [];
			});
			
			// Function to ensure autocomplete is updated
			var ensure_autocomplete = function() {
				var attr_value_field = d.fields_dict.attribute_value;
				if (!attr_value_field) return;
				
				var selected_attr = d.get_value('attribute');
				if (!selected_attr || !d._attribute_values_map[selected_attr]) return;
				
				var values = d._attribute_values_map[selected_attr];
				var $input = attr_value_field.$input || 
					(attr_value_field.control && attr_value_field.control.$input) || 
					(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input[data-fieldname="attribute_value"]')) ||
					(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input'));
				
				if ($input && $input.length > 0) {
					var input = $input[0];
					var awesomplete = attr_value_field.awesomplete ||
						(attr_value_field.control && attr_value_field.control.awesomplete) ||
						$input.data('awesomplete') ||
						input.awesomplete;
					
					if (awesomplete) {
						awesomplete.list = values;
					} else if (typeof Awesomplete !== 'undefined' && values.length > 0) {
						awesomplete = new Awesomplete(input, {
							minChars: 0,
							maxItems: 99,
							list: values
						});
						if (attr_value_field.control) {
							attr_value_field.control.awesomplete = awesomplete;
						} else {
							attr_value_field.awesomplete = awesomplete;
						}
						$input.data('awesomplete', awesomplete);
					}
				}
			};
			
			// Update on focus/click/input
			if (d.fields_dict.attribute_value) {
				var $input = d.fields_dict.attribute_value.$input || 
					(d.fields_dict.attribute_value.control && d.fields_dict.attribute_value.control.$input) ||
					(d.fields_dict.attribute_value.$wrapper && d.fields_dict.attribute_value.$wrapper.find('input'));
				if ($input && $input.length > 0) {
					$input.on('focus click input', function() {
						// Use the update function from change handler if available
						if (d._update_attribute_autocomplete) {
							d._update_attribute_autocomplete(0);
						} else {
							ensure_autocomplete();
						}
					});
				}
			}
		}, 200);
	};

	// Bulk set prices
	page.bulk_set_prices = function(values, attributes) {
		var attribute = null;
		var attribute_value = null;
		
		if (values.attribute && values.attribute_value) {
			var attr_obj = attributes.find(function(a) {
				return (a.attribute_name || a.attribute) === values.attribute;
			});
			if (attr_obj) {
				attribute = attr_obj.attribute;
				attribute_value = values.attribute_value;
			}
		}
		
		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.bulk_set_prices",
			args: {
				template_item: page.template_item,
				attribute: attribute,
				attribute_value: attribute_value,
				price_list: values.price_list,
				rate: values.rate
			},
			freeze: true,
			freeze_message: __("Setting prices..."),
			callback: function(r) {
				if (r.message) {
					frappe.show_alert({
						message: __("Price updated for {0} variant(s)", [r.message.updated]),
						indicator: 'green'
					}, 5);
					page.load_variants();
				}
			},
			error: function(r) {
				frappe.msgprint(__("Error setting prices: {0}", [r.message || "Unknown error"]));
			}
		});
	};

	// Show bulk set valuation rate dialog
	page.show_bulk_set_valuation_rate_dialog = function() {
		if (!page.template_item) {
			frappe.msgprint(__("Please select a template item first"));
			return;
		}

		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.get_template_attributes",
			args: {
				template_item: page.template_item
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					page.show_bulk_valuation_rate_dialog(r.message);
				} else {
					// No attributes, show dialog without attribute filter
					page.show_bulk_valuation_rate_dialog([]);
				}
			},
			error: function(r) {
				// Show dialog without attributes if error
				page.show_bulk_valuation_rate_dialog([]);
			}
		});
	};

	// Show bulk valuation rate dialog
	page.show_bulk_valuation_rate_dialog = function(attributes) {
		var fields = [];
		var current_attribute_values = [];
		var selected_attribute_obj = null;
		
		// Attribute field (optional) - from template item attributes
		if (attributes.length > 0) {
			var attribute_options = attributes.map(function(attr) {
				return attr.attribute_name || attr.attribute;
			}).join('\n');
			
			fields.push({
				fieldtype: 'Select',
				label: __("Attribute (Optional)"),
				fieldname: 'attribute',
				options: attribute_options,
				change: function() {
					var selected_attr = d.get_value('attribute');
					selected_attribute_obj = attributes.find(function(a) {
						return (a.attribute_name || a.attribute) === selected_attr;
					});
					if (selected_attribute_obj) {
						current_attribute_values = selected_attribute_obj.values || [];
						
						// Function to update autocomplete directly without refresh
						var update_autocomplete_direct = function() {
							var attr_value_field = d.fields_dict.attribute_value;
							if (!attr_value_field) return false;
							
							// Try set_data method first
							if (attr_value_field.set_data && typeof attr_value_field.set_data === 'function') {
								attr_value_field.set_data(current_attribute_values);
								return true;
							}
							
							if (attr_value_field.control && attr_value_field.control.set_data && typeof attr_value_field.control.set_data === 'function') {
								attr_value_field.control.set_data(current_attribute_values);
								return true;
							}
							
							// Find input element - try multiple ways
							var $input = attr_value_field.$input || 
								(attr_value_field.control && attr_value_field.control.$input) || 
								(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input[data-fieldname="attribute_value"]')) ||
								(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input')) ||
								d.$wrapper.find('input[data-fieldname="attribute_value"]');
							
							if ($input && $input.length > 0) {
								var input = $input[0];
								
								// Find existing awesomplete
								var awesomplete = attr_value_field.awesomplete ||
									(attr_value_field.control && attr_value_field.control.awesomplete) ||
									$input.data('awesomplete') ||
									input.awesomplete;
								
								if (awesomplete) {
									awesomplete.list = current_attribute_values;
									return true;
								} else if (typeof Awesomplete !== 'undefined' && current_attribute_values.length > 0) {
									// Create new awesomplete
									awesomplete = new Awesomplete(input, {
										minChars: 0,
										maxItems: 99,
										list: current_attribute_values
									});
									if (attr_value_field.control) {
										attr_value_field.control.awesomplete = awesomplete;
									} else {
										attr_value_field.awesomplete = awesomplete;
									}
									$input.data('awesomplete', awesomplete);
									return true;
								}
							}
							return false;
						};
						
						// Update options
						d.set_df_property('attribute_value', 'options', current_attribute_values);
						d.set_value('attribute_value', '');
						
						// Try to update immediately
						if (!update_autocomplete_direct()) {
							// If failed, refresh field and try again
							d.refresh_field('attribute_value');
							setTimeout(function() {
								update_autocomplete_direct();
							}, 400);
						}
						
						// Store update function on dialog
						d._update_attribute_autocomplete = update_autocomplete_direct;
					}
				}
			});
			
			fields.push({
				fieldtype: 'Autocomplete',
				label: __("Attribute Value (Optional)"),
				fieldname: 'attribute_value',
				options: []
			});
		}
		
		fields.push({
			fieldtype: 'Currency',
			label: __("Valuation Rate"),
			fieldname: 'valuation_rate',
			reqd: 1
		});

		var d = new frappe.ui.Dialog({
			title: __("Bulk Set Valuation Rate"),
			fields: fields,
			primary_action_label: __("Set Valuation Rate"),
			primary_action: function(values) {
				d.hide();
				page.bulk_set_valuation_rates(values, attributes);
			},
			onhide: function() {
				// Clean up when dialog is closed
				selected_attribute_obj = null;
				current_attribute_values = [];
			}
		});

		// Fix z-index to appear above buttons
		d.$wrapper.css('z-index', '1050');
		
		d.show();
		
		// After dialog is shown, set up autocomplete update mechanism
		setTimeout(function() {
			// Store reference to attributes for use in update function
			d._attribute_values_map = {};
			attributes.forEach(function(attr) {
				var key = attr.attribute_name || attr.attribute;
				d._attribute_values_map[key] = attr.values || [];
			});
			
			// Function to ensure autocomplete is updated
			var ensure_autocomplete = function() {
				var attr_value_field = d.fields_dict.attribute_value;
				if (!attr_value_field) return;
				
				var selected_attr = d.get_value('attribute');
				if (!selected_attr || !d._attribute_values_map[selected_attr]) return;
				
				var values = d._attribute_values_map[selected_attr];
				var $input = attr_value_field.$input || 
					(attr_value_field.control && attr_value_field.control.$input) || 
					(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input[data-fieldname="attribute_value"]')) ||
					(attr_value_field.$wrapper && attr_value_field.$wrapper.find('input'));
				
				if ($input && $input.length > 0) {
					var input = $input[0];
					var awesomplete = attr_value_field.awesomplete ||
						(attr_value_field.control && attr_value_field.control.awesomplete) ||
						$input.data('awesomplete') ||
						input.awesomplete;
					
					if (awesomplete) {
						awesomplete.list = values;
					} else if (typeof Awesomplete !== 'undefined' && values.length > 0) {
						awesomplete = new Awesomplete(input, {
							minChars: 0,
							maxItems: 99,
							list: values
						});
						if (attr_value_field.control) {
							attr_value_field.control.awesomplete = awesomplete;
						} else {
							attr_value_field.awesomplete = awesomplete;
						}
						$input.data('awesomplete', awesomplete);
					}
				}
			};
			
			// Update on focus/click/input
			if (d.fields_dict.attribute_value) {
				var $input = d.fields_dict.attribute_value.$input || 
					(d.fields_dict.attribute_value.control && d.fields_dict.attribute_value.control.$input) ||
					(d.fields_dict.attribute_value.$wrapper && d.fields_dict.attribute_value.$wrapper.find('input'));
				if ($input && $input.length > 0) {
					$input.on('focus click input', function() {
						// Use the update function from change handler if available
						if (d._update_attribute_autocomplete) {
							d._update_attribute_autocomplete(0);
						} else {
							ensure_autocomplete();
						}
					});
				}
			}
		}, 200);
	};

	// Bulk set valuation rates
	page.bulk_set_valuation_rates = function(values, attributes) {
		var attribute = null;
		var attribute_value = null;
		
		if (values.attribute && values.attribute_value) {
			var attr_obj = attributes.find(function(a) {
				return (a.attribute_name || a.attribute) === values.attribute;
			});
			if (attr_obj) {
				attribute = attr_obj.attribute;
				attribute_value = values.attribute_value;
			}
		}
		
		frappe.call({
			method: "erpnext.item_variant_manager.api.item_variant_manager.bulk_set_valuation_rates",
			args: {
				template_item: page.template_item,
				attribute: attribute,
				attribute_value: attribute_value,
				valuation_rate: values.valuation_rate
			},
			freeze: true,
			freeze_message: __("Setting valuation rates..."),
			callback: function(r) {
				if (r.message) {
					frappe.show_alert({
						message: __("Valuation rate updated for {0} variant(s)", [r.message.updated]),
						indicator: 'green'
					}, 5);
					page.load_variants();
				}
			},
			error: function(r) {
				frappe.msgprint(__("Error setting valuation rates: {0}", [r.message || "Unknown error"]));
			}
		});
	};

	// Show stock management dialog
	page.show_stock_management_dialog = function(variant_code, warehouse, current_qty) {
		// Prevent opening multiple dialogs
		if (page.stockManagementDialogOpen) {
			return;
		}
		
		var fields = [
			{
				fieldtype: 'Section Break',
				label: __("Stock Management Options")
			},
			{
				fieldtype: 'Select',
				label: __("Action Type"),
				fieldname: 'action_type',
				options: __("Stock Reconciliation (Correct Stock)\nStock Entry (Add/Remove Stock)"),
				reqd: 1,
				default: 'Stock Reconciliation (Correct Stock)'
			},
			{
				fieldtype: 'Column Break'
			},
			{
				fieldtype: 'Float',
				label: __("Current Stock"),
				fieldname: 'current_qty',
				default: current_qty,
				read_only: 1
			},
			{
				fieldtype: 'Section Break'
			},
			{
				fieldtype: 'Float',
				label: __("Quantity"),
				fieldname: 'qty',
				reqd: 1,
				description: __("For Stock Reconciliation: Set the exact quantity. For Stock Entry: Enter the quantity to add (positive) or remove (negative).")
			},
			{
				fieldtype: 'Column Break'
			},
			{
				fieldtype: 'Data',
				label: __("Item Code"),
				fieldname: 'item_code',
				default: variant_code,
				read_only: 1
			},
			{
				fieldtype: 'Link',
				label: __("Warehouse"),
				fieldname: 'warehouse',
				options: 'Warehouse',
				default: warehouse,
				reqd: 1,
				get_query: function() {
					var company = page.company_field ? page.company_field.get_value() : null;
					if (company) {
						return {
							filters: {
								company: company,
								is_group: 0
							}
						};
					}
					return {
						filters: {
							is_group: 0
						}
					};
				}
			}
		];

		var d = new frappe.ui.Dialog({
			title: __("Manage Stock"),
			fields: fields,
			primary_action_label: __("Proceed"),
			primary_action: function(values) {
				d.hide();
				page.process_stock_management(variant_code, warehouse, values);
			},
			onhide: function() {
				// Clear flag when dialog is closed
				page.stockManagementDialogOpen = false;
			}
		});

		// Set flag before showing
		page.stockManagementDialogOpen = true;
		d.show();
	};

	// Process stock management action
	page.process_stock_management = function(variant_code, warehouse, values) {
		var company = page.company_field ? page.company_field.get_value() : null;
		
		// Determine action type from selected value
		var is_reconcile = values.action_type === 'Stock Reconciliation (Correct Stock)' || values.action_type === 'reconcile';
		
		if (is_reconcile) {
			// Stock Reconciliation
			frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.update_stock_qty",
				args: {
					variant_code: variant_code,
					warehouse: values.warehouse || warehouse,
					qty: values.qty,
					company: company
				},
				freeze: true,
				freeze_message: __("Reconciling stock..."),
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: __("Stock reconciled to {0}", [values.qty]),
							indicator: 'green'
						}, 3);
						page.load_variants();
					}
				},
				error: function(r) {
					var error_msg = r.message || "Unknown error";
					if (typeof error_msg === 'string') {
						frappe.msgprint(__("Error reconciling stock: {0}", [error_msg]));
					} else if (error_msg.exc_type) {
						frappe.msgprint(__("Error reconciling stock: {0}", [error_msg.exc_message || error_msg.exc_type]));
					} else if (error_msg.message) {
						frappe.msgprint(__("Error reconciling stock: {0}", [error_msg.message]));
					} else {
						frappe.msgprint(__("Error reconciling stock: {0}", [JSON.stringify(error_msg)]));
					}
				}
			});
		} else {
			// Stock Entry - create via API and submit (same as Stock Reconciliation)
			frappe.call({
				method: "erpnext.item_variant_manager.api.item_variant_manager.create_stock_entry",
				args: {
					variant_code: variant_code,
					warehouse: values.warehouse || warehouse,
					qty: values.qty,
					company: company
				},
				freeze: true,
				freeze_message: __("Creating and submitting Stock Entry..."),
				callback: function(r) {
					if (r.message && r.message.success) {
						var entry_type = parseFloat(values.qty) > 0 ? __("Material Receipt") : __("Material Issue");
						frappe.show_alert({
							message: __("Stock Entry {0} ({1}) created and submitted", [r.message.stock_entry, entry_type]),
							indicator: 'green'
						}, 3);
						page.load_variants();
					}
				},
				error: function(r) {
					var error_msg = r.message || "Unknown error";
					if (typeof error_msg === 'string') {
						frappe.msgprint(__("Error creating Stock Entry: {0}", [error_msg]));
					} else if (error_msg.exc_type) {
						frappe.msgprint(__("Error creating Stock Entry: {0}", [error_msg.exc_message || error_msg.exc_type]));
					} else if (error_msg.message) {
						frappe.msgprint(__("Error creating Stock Entry: {0}", [error_msg.message]));
					} else {
						frappe.msgprint(__("Error creating Stock Entry: {0}", [JSON.stringify(error_msg)]));
					}
				}
			});
		}
	};
};
