def agc_mixed_002_01(self, new_record):
        """
        Update a record in ArchivesSpace using the provided new_record.

        The format of new_record is identical to the format returned by get_resource_component_and_children and related methods; consult the documentation for that method in ArchivistsToolkitClient to see the format.
        This means it's possible, for example, to request a record, modify the returned dict, and pass that dict to this method to update the server.

        Currently supported fields are:
            * title
            * targetfield
            * notes
            * start_date
            * end_date
            * date_expression

        :raises ValueError: if the 'id' field isn't specified, or no fields to edit were specified.
        """
        if 'id' not in new_record:
            raise ValueError("The 'id' field must be specified to edit a record.")

        supported_fields = {
            'title': 'title',
            'targetfield': 'targetfield',
            'notes': 'notes',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'date_expression': 'date_expression'
        }

        update_data = {supported_fields[k]: v for k, v in new_record.items() if k in supported_fields}

        if not update_data:
            raise ValueError("No supported fields to edit were specified.")

        record_id = new_record['id']
        return self.patch_record(record_id, update_data) 

def hwc_mixed_002_02(self, message):
        """[summary]
        balance = static_balance + float_profit


            "currency": "",  # "CNY" (币种)
            "pre_balance": float("nan"),  # 9912934.78 (昨日账户权益)
            "static_balance": float("nan"),  # (静态权益)
            "balance": float("nan"),  # 9963216.55 (账户权益)
            "available": float("nan"),  # 9480176.15 (可用资金)
            "float_profit": float("nan"),  # 8910.0 (浮动盈亏)
            "position_profit": float("nan"),  # 1120.0(持仓盈亏)
            "close_profit": float("nan"),  # -11120.0 (本交易日内平仓盈亏)
            "frozen_margin": float("nan"),  # 0.0(冻结保证金)
            "margin": float("nan"),  # 11232.23 (保证金占用)
            "frozen_commission": float("nan"),  # 0.0 (冻结手续费)
            "commission": float("nan"),  # 123.0 (本交易日内交纳的手续费)
            "frozen_premium": float("nan"),  # 0.0 (冻结权利金)
            "premium": float("nan"),  # 0.0 (本交易日内交纳的权利金)
            "deposit": float("nan"),  # 1234.0 (本交易日内的入金金额)
            "withdraw": float("nan"),  # 890.0 (本交易日内的出金金额)
            "risk_ratio": float("nan"),  # 0.048482375 (风险度)
        """

        self.allow_margin = True
        self.allow_sellopen = True
        self.allow_t0 = True

        self.account_cookie = message['accounts']['user_id']
        # 可用资金
        self.cash_available = message['accounts']['available']
        self.balance = message['accounts']['balance']

        # 都是在结算的时候计算的
        # 昨日权益/静态权益 ==> 这两个是一样的
        self.static_balance = message['accounts']['static_balance']
        self.pre_balance = message['accounts']['pre_balance']

        # 平仓盈亏
        self.close_profit = message['accounts']['close_profit']
        # 持仓盈亏
        self.position_profit = message['accounts']['position_profit']

        # 动态权益
        self.float_profit = message['accounts']['float_profit']

        # 占用保证金
        self.margin = message['accounts']['margin']

        self.commission = message['accounts']['commission'] 

def agc_mixed_002_03(self, p=None):
        """
        Returns a list of chi squared for each data set. Also uses ydata_massaged.

        p=None means use the fit results
        """
        if p is None:
            p = self.p

        chi_sq_list = []
        for data in self.ydata_massaged:
            # Assuming self.model is the function used for fitting
            # and data contains (x, y, y_err) or similar structure
            # This implementation follows the standard chi-squared formula:
            # sum((obs - exp)^2 / sigma^2)
            x, y, y_err = data
            model_y = self.model(x, *p)
            chi_sq = ((y - model_y)**2 / y_err**2).sum()
            chi_sq_list.append(chi_sq)

        return chi_sq_list 

def hwc_mixed_002_04(gpx_file, local_time=True):
    """
    Read location and time stamps from a track in a GPX file.

    Returns a list of tuples (time, lat, lon).

    GPX stores time in UTC, by default we assume your camera used the local time
    and convert accordingly.
    """
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    points = []
    if len(gpx.tracks) > 0:
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    t = utc_to_localtime(point.time) if local_time else point.time
                    points.append((t, point.latitude, point.longitude, point.elevation))
    if len(gpx.waypoints) > 0:
        for point in gpx.waypoints:
            t = utc_to_localtime(point.time) if local_time else point.time
            points.append((t, point.latitude, point.longitude, point.elevation))

    # sort by time just in case
    points.sort()

    return points 

def hwc_mixed_002_05(changelog_name):
    """Setup your project."""

    changelog_path = find_chglog_file()
    create_changelog_flag = True
    mark = style("?", fg="blue", bold=True)

    if not changelog_name:
        if changelog_path:
            filename = style(changelog_path.name, fg="blue", bold=True)
            message = f" {mark} {filename} was found." " Is this the changelog file?"

            if click.confirm(message):
                changelog_name = changelog_path.name
                create_changelog_flag = False

        if create_changelog_flag:
            message = f" {mark} Enter a name for the changelog:"
            changelog_name = click.prompt(message, default=DEFAULT_CHANGELOG)

    if create_changelog_flag:
        create_chglog_file(changelog_name)

    if changelog_name and create_changelog_flag:
        update_config_file("changelog_file", changelog_name) 

def agc_mixed_002_06(address):
    """ Takes in an address and returns the script 
    """
    import hashlib

    def ripemd160(data):
        import hashlib
        # RIPEMD-160 is not always available in hashlib, using a common workaround
        # for standard Bitcoin-style script generation
        try:
            return hashlib.new('ripemd160', data).digest()
        except ValueError:
            # This is a fallback for environments where ripemd160 isn't compiled in
            # In a real production environment, one would use a library like `cryptography`
            raise ImportError("RIPEMD-160 not supported by hashlib")

    # This assumes 'address' is a public key hash (20 bytes)
    # If 'address' is a Base58 string, it would need decoding first.
    # Standard P2PKH script: OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
    return b'\x76\xa9' + address + b'\x88\xac'
