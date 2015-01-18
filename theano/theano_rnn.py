import theano
import theano.tensor as T
from theano_utils import randn, NP_FLOATX
from theano_nn import SquaredLoss, TanhLayer, SigmLayer, SoftMaxLayer
import numpy as np

__author__ = 'justin'


class BaseLayer(object):
    n_instances = 0

    def __init__(self):
        self.layer_id = BaseLayer.n_instances
        BaseLayer.n_instances += 1

    def forward_time(self, prev_layer, prev_state):
        """
        Run a forward pass for a single layer and single time step
        :param prev_layer:
        :param prev_state:
        :return: (next_layer, next_state)
        """
        raise NotImplementedError

    def initial_state(self):
        raise NotImplementedError

    def params(self):
        """ Return a list of trainable parameters """
        return []


class FeedForwardLayer(BaseLayer):
    """
    A special adapter for feedforward networks
    """
    def __init__(self):
        super(FeedForwardLayer, self).__init__()
        self.zero = theano.shared(0)

    def forward(self, prev_layer):
        raise NotImplementedError

    def forward_time(self, prev_layer, prev_state):
        return self.forward(prev_layer), self.zero

    def initial_state(self):
        return self.zero  # Unused


class ActivationLayer(FeedForwardLayer):
    def __init__(self, act):
        super(ActivationLayer, self).__init__()
        self.act = act


class FFIPLayer(FeedForwardLayer):
    """ Feedforward inner product layer """
    def __init__(self, n_in, n_out):
        super(FFIPLayer, self).__init__()
        self.w = theano.shared(randn(n_in, n_out), name="ff_ip_w_"+str(self.layer_id))
        self.b = theano.shared(randn(n_out), name="b_ip"+str(self.layer_id))

    def forward(self, prev_layer):
        return prev_layer.dot(self.w) + self.b

    def params(self):
        """ Return a list of trainable parameters """
        return [self.w, self.b]


class RNNIPLayer(BaseLayer):
    """ Recurrent inner product layer """
    def __init__(self, n_in, n_out, act):
        super(RNNIPLayer, self).__init__()
        self.n_out = n_out
        self.w_ff = theano.shared(randn(n_in, n_out), name="rnn_ip_wff_"+str(self.layer_id))
        self.w_r = theano.shared(randn(n_out, n_out), name="rnn_ip_wr_"+str(self.layer_id))
        self.act = act

    def forward_time(self, prev_layer, prev_state):
        new_state = self.w_r.dot(prev_state)
        output = self.act(prev_layer.dot(self.w_ff)+new_state)
        return output, output+0

    def initial_state(self):
        #return np.zeros((self.n_out, 1))  <---- This produces very different numbers
        return theano.shared(np.zeros(self.n_out))

    def params(self):
        """ Return a list of trainable parameters """
        return [self.w_ff, self.w_r]


class LSTMLayer(BaseLayer):
    def __init__(self):
        super(LSTMLayer, self).__init__()
        #TODO: Copy implementation from code in master
        raise NotImplementedError


class RecurrentNetwork(object):
    def __init__(self, layers, loss):
        self.layers = layers
        self.loss = loss

        #setup for gradients
        self.params_list = []
        for layer in layers:
            self.params_list.extend(layer.params())

    def params(self):
        return self.params_list

    def predict(self):
        x = T.matrix('X')
        pred = theano.function([x], self.forward_across_time(x))
        return pred

    def forward_across_time(self, training_ex):
        previous_layer = training_ex
        for layer in self.layers:
            hidden_state = layer.initial_state()

            def loop(prev_layer, prev_state):
                nlayer, nstate = layer.forward_time(prev_layer, prev_state)
                return nlayer, nstate

            results, updates = theano.scan(fn=loop,
                                            sequences=[previous_layer],
                                            outputs_info=[None, hidden_state])
            next_layer, hidden_states = results
            previous_layer = next_layer


            """
            n_timestep, n_dim = previous_layer.shape
            for t in range(n_timestep):
                next_layer, hidden_state = loop(previous_layer[i], hidden_state)
            """

        return previous_layer

    def prepare_objective(self, data, labels):
        # data is a list of matrices
        obj = None
        for i in range(len(data)):
            training_ex = data[i]
            label = theano.shared(labels[i])
            net_output = self.forward_across_time(theano.shared(training_ex))
            layer_loss = self.loss.loss(label, net_output)
            if obj:
                obj += layer_loss
            else:
                obj = layer_loss
        return obj


def train_gd(trainable, eta=0.01):
    obj = trainable.obj
    params = trainable.params
    gradients = T.grad(obj, params)
    updates = [None]*len(gradients)

    for i in range(len(gradients)):
        updates[i] = (params[i], params[i]-eta*gradients[i])

    train = theano.function(
        inputs=trainable.args(),
        outputs=[obj],
        updates=updates
    )
    return train


def train_gd_host(trainable, data, labels, eta=0.01):
    obj = trainable.prepare_objective(data, labels)
    params = trainable.params()
    print 'PARAMS:', params
    gradients = T.grad(obj, params)
    updates = [None]*len(gradients)

    for i in range(len(gradients)):
        updates[i] = (params[i], params[i]-eta*gradients[i])

    train = theano.function(
        inputs=[],
        outputs=[obj],
        updates=updates)
    return train


def generate_parity_data(num):
    examples = []
    labels = []
    for i in range(num):
        N = np.random.randint(low=3, high=10)

        rand_data = np.random.randint(size=(N, 1), low=0, high=2).astype(np.float32)

        rand_label = np.cumsum(rand_data, axis=0) % 2
        #rand_data = np.hstack((rand_data, rand_label))


        examples.append(rand_data)
        labels.append(rand_label)
    return examples, labels


def test_rnn():
    data, labels = generate_parity_data(1)
    print "DATA:", data[0]
    data = theano.shared(data[0])
    label = theano.shared(labels[0])

    w = theano.shared(randn(2, 1))

    def fff(prev_layer, prev_state):
        #import pdb; pdb.set_trace()
        print prev_state
        print prev_layer
        print w.get_value()
        output = prev_layer.dot(w)+prev_state
        return output, output+0

    results, updates = theano.scan(
        fn=fff,
        outputs_info=[None, theano.shared(np.ones((1)))],
        sequences=[data])

    blah = theano.function(inputs=[], outputs=results)

    a = blah()
    print 'Output:', a

    loss = SquaredLoss().loss(label, results[0])
    blah = theano.function(inputs=[], outputs=loss)
    print blah()

    gd = T.grad(loss, [w])
    blah = theano.function(inputs=[], outputs=gd)
    print 'gradient:', blah()

if __name__ == "__main__":
    np.random.seed(10)

    """
    x = T.scalar('x')
    k = T.scalar('k')

    def f(i, xx):
        return xx+k, k

    results, updates = theano.scan(
        fn=f,
        outputs_info=[np.array(0.0), None],
        sequences=T.arange(5))
    blah = theano.function(inputs=[k], outputs=results, updates=updates)
    print blah(1)
    """

    #test_rnn()

    #TODO:
    # - Use theano's typed_list instead of python lists
    # - Don't use shared variables on data/labels in forward pass loop (supply them as function args)

    #"""
    data, labels = generate_parity_data(5)
    print 'data:', data[0].T

    l1 = RNNIPLayer(1, 2, T.tanh)
    l2 = RNNIPLayer(2, 1, T.nnet.sigmoid)


    rnn = RecurrentNetwork([l1, l2], SquaredLoss())
    p = rnn.predict()

    ob = rnn.prepare_objective(data, labels)
    fff = theano.function([], ob)

    print p(data[0])
    train_fn = train_gd_host(rnn, data, labels, eta=0.1)

    for i in range(800):
        loss = train_fn()[0]
        if i % 5 == 0:
            print i, ':', loss


    print labels[0]
    p = rnn.predict()
    print p(data[0])

    # Check for generalization
    data, labels = generate_parity_data(2)
    for i in range(len(data)):
        predicted = p(data[0])
        print 'New Data:', data[0]
        print "New Labels:",labels[0]
        print "New predict:", predicted
    #"""