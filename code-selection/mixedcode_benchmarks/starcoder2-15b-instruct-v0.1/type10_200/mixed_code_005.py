def agc_mixed_005_01(self, market, stock_type=SecurityType.STOCK, code_list=None):
        """
        获取指定市场中特定类型的股票基本信息
        :param market: 市场类型，futuquant.common.constant.Market
        :param stock_type: 股票类型， futuquant.common.constant.SecurityType
        :param code_list: 如果不为None，应该是股票code的iterable类型，将只返回指定的股票信息
        :return: (ret_code, content)
                ret_code 等于RET_OK时， content为Pandas.DataFrame数据, 否则为错误原因字符串, 数据列格式如下
            =================   ===========   ==============================================================================
            参数                  类型                        说明
            =================   ===========   ==============================================================================
            code                str            股票代码
            name                str            名字
            lot_size            int            每手数量
            stock_type          str            股票类型，参见SecurityType
            stock_child_type    str            涡轮子类型，参见WrtType
            stock_owner         str            所属正股的代码
            option_type         str            期权类型，Qot_Common.OptionType
            strike_time         str            行权日
            strike_price        float          行权价
            suspension          bool           是否停牌(True表示停牌)
            listing_date        str            上市时间
            stock_id            int            股票id
            delisting           bool           是否退市
            =================   ===========   ==============================================================================

        :example:

            .. code-block:: python

            from futuquant import *
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            print(quote_ctx.get_stock_basicinfo(Market.HK, SecurityType.WARRANT))
            print(quote_ctx.get_stock_basicinfo(Market.US, SecurityType.DRVT, 'US.AAPL190621C140000'))
            quote_ctx.close()
        """
        if code_list is not None:
            code_list = list(code_list)
        else:
            code_list = []
        ret, data = self._get_stock_basicinfo(market, stock_type, code_list)
        if ret!= RET_OK:
            return ret, data
        df = pd.DataFrame(data, columns=['code', 'name', 'lot_size','stock_type','stock_child_type','stock_owner',
                                         'option_type','strike_time','strike_price','suspension', 'listing_date',
                                        'stock_id', 'delisting'])
        return RET_OK, df 

def agc_mixed_005_02(value):
    """
    Transform an access flag field to the corresponding string

    :param value: the value of the access flags
    :type value: int

    :rtype: string
    """
    access_flags = {
        0x0001: "public",
        0x0002: "private",
        0x0004: "protected",
        0x0008: "static",
        0x0010: "final",
        0x0020: "synchronized",
        0x0040: "bridge",
        0x0080: "varargs",
        0x0100: "native",
        0x0400: "abstract",
        0x0800: "strict",
        0x1000: "synthetic",
        0x2000: "annotation",
        0x4000: "enum",
        0x8000: "interface",
        0x10000: "module"
    }
    flags = []
    for flag, flag_string in access_flags.items():
        if value & flag:
            flags.append(flag_string)
    return " ".join(flags) 

def hwc_mixed_005_03(self, obj, name, data, inplace=True, context=None):
        """Deserialize data from primitive types updating existing object.
        Raises :exc:`~lollipop.errors.ValidationError` if data is invalid.

        :param obj: Object to update with deserialized data.
        :param str name: Name of attribute to deserialize.
        :param data: Raw data to get value to deserialize from.
        :param bool inplace: If True update data inplace;
            otherwise - create new data.
        :param kwargs: Same keyword arguments as for :meth:`load`.
        :returns: Loaded data.
        :raises: :exc:`~lollipop.errors.ValidationError`
        """
        if obj is None:
            raise ValueError('Load target should not be None')

        value = data.get(name, MISSING)

        if value is MISSING:
            return

        target = self.get_value(name, obj, context=context)
        if target is not None and target is not MISSING \
                and hasattr(self.field_type, 'load_into'):
            return self.field_type.load_into(target, value, inplace=inplace,
                                             context=context)
        else:
            return self.field_type.load(value, context=context) 

def hwc_mixed_005_04(self):
        """ validate: Makes sure video is valid
            Args: None
            Returns: boolean indicating if video is valid
        """
        from .files import VideoFile, WebVideoFile
        try:
            assert self.kind == content_kinds.VIDEO, "Assumption Failed: Node should be a video"
            assert self.questions == [], "Assumption Failed: Video should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Video must have at least one video file"

            # Check if there are any .mp4 files if there are video files (other video types don't have paths)
            assert any(f for f in self.files if isinstance(f, VideoFile) or isinstance(f, WebVideoFile)), "Assumption Failed: Video should have at least one .mp4 file"

            return super(VideoNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__)) 

def agc_mixed_005_05(self, attributes=values.unset, assignment_status=values.unset,
               reason=values.unset, priority=values.unset,
               task_channel=values.unset):
        """
        Update the TaskInstance

        :param unicode attributes: The user-defined JSON data describing the custom attributes of this task.
        :param TaskInstance.Status assignment_status: A 'pending' or 'reserved' Task may be canceled by posting AssignmentStatus='canceled'.
        :param unicode reason: This is only required if the Task is canceled or completed.
        :param unicode priority: Override priority for the Task.
        :param unicode task_channel: The task_channel

        :returns: Updated TaskInstance
        :rtype: twilio.rest.taskrouter.v1.workspace.task.TaskInstance
        """
        data = values.of({})

        if attributes is not values.unset:
            data["Attributes"] = attributes
        if assignment_status is not values.unset:
            data["AssignmentStatus"] = assignment_status
        if reason is not values.unset:
            data["Reason"] = reason
        if priority is not values.unset:
            data["Priority"] = priority
        if task_channel is not values.unset:
            data["TaskChannel"] = task_channel

        return self._version.update(
            method="POST",
            uri=self._uri,
            data=data,
        ) 

def hwc_mixed_005_06(seed=default_seed, max_iters=100, optimize=True, plot=True):
    """
    Simple 1D classification example using a heavy side gp transformation

    :param seed: seed value for data generation (default is 4).
    :type seed: int

    """

    try:import pods
    except ImportError:print('pods unavailable, see https://github.com/sods/ods for example datasets')
    data = pods.datasets.toy_linear_1d_classification(seed=seed)
    Y = data['Y'][:, 0:1]
    Y[Y.flatten() == -1] = 0

    # Model definition
    kernel = GPy.kern.RBF(1)
    likelihood = GPy.likelihoods.Bernoulli(gp_link=GPy.likelihoods.link_functions.Heaviside())
    ep = GPy.inference.latent_function_inference.expectation_propagation.EP()
    m = GPy.core.GP(X=data['X'], Y=Y, kernel=kernel, likelihood=likelihood, inference_method=ep, name='gp_classification_heaviside')
    #m = GPy.models.GPClassification(data['X'], likelihood=likelihood)

    # Optimize
    if optimize:
        # Parameters optimization:
        for _ in range(5):
            m.optimize(max_iters=int(max_iters/5))
        print(m)

    # Plot
    if plot:
        from matplotlib import pyplot as plt
        fig, axes = plt.subplots(2, 1)
        m.plot_f(ax=axes[0])
        m.plot(ax=axes[1])

    print(m)
    return m
