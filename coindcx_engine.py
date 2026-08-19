def execute_trade(
        self,
        pair,
        side,
        quantity,
        price,
        market_type='futures',
        leverage=1,
        trade_mode='PAPER',
    ):
      if trade_mode == 'PAPER':
        fee_rate = 0.0005 if market_type == 'futures' else 0.001
        estimated_fee = (quantity * price) * fee_rate
        return {
            'status': 'SUCCESS',
            'mode': 'PAPER',
            'pair': pair,
            'side': side,
            'quantity': quantity,
            'entry_price': price,
            'market_type': market_type,
            'leverage': leverage,
            'fee_deducted_inr': round(estimated_fee, 2),
        }

      # Fetch Live CoinDCX Server Timestamp to avoid local clock drift
      try:
        time_res = requests.get(
            f'{BASE_URL}/exchange/v1/time', timeout=3
        ).json()
        server_timestamp = time_res.get('server_time', int(time.time() * 1000))
      except Exception:
        server_timestamp = int(time.time() * 1000)

      endpoint = (
          '/exchange/v1/orders/create'
          if market_type == 'spot'
          else '/exchange/v1/derivatives/futures/orders/create'
      )

      body = {
          'side': side.lower(),
          'order_type': 'limit_order',
          'price': float(price),
          'total_quantity': float(quantity),
          'timestamp': server_timestamp,
      }

      if market_type == 'spot':
        body['market'] = pair
      else:
        body['pair'] = pair
        body['leverage'] = leverage

      json_body = json.dumps(body, separators=(',', ':'))
      signature = self._generate_signature(json_body)

      headers = {
          'Content-Type': 'application/json',
          'X-AUTH-APIKEY': str(self.api_key).strip(),
          'X-AUTH-SIGNATURE': signature,
      }

      try:
        res = requests.post(
            BASE_URL + endpoint, headers=headers, data=json_body, timeout=10
        )
        return res.json()
      except Exception as e:
        return {'status': 'FAILED', 'error': str(e)}
