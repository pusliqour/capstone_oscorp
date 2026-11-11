"""Map ML store/SKU identifiers to storefront records and publish atomically."""

def all_rows(client, table, columns):
    rows = []
    for offset in range(0, 1_000_000, 1000):
        batch = client.table(table).select(columns).range(offset, offset+999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
    raise RuntimeError('Unexpected table size')


def publish_results(client, result, *, include_transfers=True):
    retailers = {r['id']: r['store_id'] for r in all_rows(client, 'retailer_profiles', 'id,store_id')}
    products = {r['id']: r for r in all_rows(client, 'products', 'id,sku,retailer_id,pos_connection_id')}
    lookup = {}
    for v in all_rows(client, 'product_variations', 'id,product_id'):
        p = products[v['product_id']]
        key = (retailers.get(p['retailer_id']), p['sku'])
        if key in lookup:
            raise ValueError(f'Ambiguous storefront mapping: {key}')
        lookup[key] = {'retailer_id': p['retailer_id'], 'pos_connection_id': p['pos_connection_id'], 'product_variation_id': v['id']}
    predictions = []
    for p in result.get('predictions', result.get('results', [])):
        key = (p['store_id'], p['product_id'])
        if key not in lookup:
            raise ValueError(f'Prediction has no storefront mapping: {key}')
        predictions.append({**lookup[key], **{k: p[k] for k in ('product_name', 'prediction', 'confidence', 'model_prediction', 'decision_source', 'demand_30d', 'demand_source', 'stock_plan')}})
    if not predictions:
        raise ValueError('Refusing to publish empty predictions')
    transfers = []
    fields = ('product_name', 'transfer_qty', 'from_label', 'to_label', 'from_stock_before', 'from_stock_after', 'to_stock_before', 'to_stock_after', 'demand_30d', 'from_coverage_after', 'to_coverage_after')
    if include_transfers:
        for t in result.get('transfers', []):
            row = {k: t[k] for k in fields}
            for side in ('from', 'to'):
                mapped = lookup[(t[f'{side}_store'], t['product_id'])]
                row.update({f'{side}_{k}': v for k, v in mapped.items()})
            transfers.append(row)
    return client.rpc('publish_ml_results', {'prediction_rows': predictions, 'transfer_rows': transfers, 'replace_transfers': include_transfers}).execute().data
