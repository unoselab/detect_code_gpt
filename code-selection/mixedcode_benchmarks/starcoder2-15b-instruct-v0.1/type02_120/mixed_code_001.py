def agc_mixed_001_01(self, value):
        """
        Ensures that the password follows the following criteria:

        :param value: <str>

        :return: True
        """
        if len(value) < 8:
            return False
        if not any(c.isupper() for c in value):
            return False
        if not any(c.islower() for c in value):
            return False
        if not any(c.isdigit() for c in value):
            return False
        return True 

def agc_mixed_001_02(freq):
    """Huffman code

    :param freq: dictionary with frequencies for each item
    :returns: dictionary with binary code string for each item
    :complexity: O(n log n)
    """
    heap = [[weight, [symbol, '']] for symbol, weight in freq.items()]
    heapq.heapify(heap)
    while len(heap) > 1:
        lo = heapq.heappop(heap)
        hi = heapq.heappop(heap)
        for pair in lo[1:]:
            pair[1] = '0' + pair[1]
        for pair in hi[1:]:
            pair[1] = '1' + pair[1]
        heapq.heappush(heap, [lo[0] + hi[0]] + lo[1:] + hi[1:])
    return dict(heapq.heappop(heap)[1:]) 

def hwc_mixed_001_03(self, batch_info: BatchInfo):
        """ Perform an 'on-policy' training step of evaluating an env and a single backpropagation step """
        self.model.train()

        rollout = self.env_roller.rollout(batch_info, self.model, self.settings.number_of_steps).to_device(self.device)

        batch_result = self.algo.optimizer_step(
            batch_info=batch_info,
            device=self.device,
            model=self.model,
            rollout=rollout
        )

        batch_info['sub_batch_data'].append(batch_result)
        batch_info['frames'] = rollout.frames()
        batch_info['episode_infos'] = rollout.episode_information() 

def hwc_mixed_001_04(self):
        """
        Overridden to open the left and right zipfiles and to provide all
        subchecks with an open ZipFile instance rather than having
        them all open and close the ZipFile individually. For the
        duration of the check (which calls collect_impl), the
        attributes self.lzip and self.rzip will be available and used
        as the ldata and rdata of all subchecks.
        """

        with open_zip(self.ldata) as lzip:
            with open_zip(self.rdata) as rzip:
                self.lzip = lzip
                self.rzip = rzip
                ret = super(JarContentsChange, self).check_impl()

        self.lzip = None
        self.rzip = None

        return ret 

def hwc_mixed_001_05(request, chat_channel_name=None):
    """
        if we have a chat_channel_name kwarg,
        have the response include that channel name
        so the javascript knows to subscribe to that
        channel...
    """

    if not chat_channel_name:
        chat_channel_name = 'homepage'

    context = {
        'address': chat_channel_name,
        'history': [],
    }

    if ChatMessage.objects.filter(channel=chat_channel_name).exists():
        context['history'] = ChatMessage.objects.filter(
            channel=chat_channel_name)


    # TODO add https 
    websocket_prefix = "ws"
    websocket_port = 9000

    context['websocket_prefix'] = websocket_prefix
    context['websocket_port'] = websocket_port

    return render(request, 'chat.html', context) 

def agc_mixed_001_06(handle, uplo, n, alpha, x, incx, A, lda): 
    """
    Rank-1 operation on real symmetric matrix.

    """

    if uplo == 'U':
        for i in range(n):
            for j in range(i, n):
                A[i, j] += alpha * x[i * incx] * x[j * incx]
    else:
        for i in range(n):
            for j in range(i):
                A[i, j] += alpha * x[i * incx] * x[j * incx]
