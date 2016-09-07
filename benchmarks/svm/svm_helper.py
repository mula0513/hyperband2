import os
import sys
import numpy as np
import time
import HPOlib.benchmark_util as benchmark_util
import HPOlib.wrapping_util as wrapping_util
from sklearn import svm,preprocessing

def create_dataset(data_name,data_dir,combine=False):
    # This function loads the MNIST data, its copied from the Lasagne tutorial
    # We first define a download function, supporting both Python 2 and 3.
    if data_name=='mnist':
        if sys.version_info[0] == 2:
            from urllib import urlretrieve
        else:
            from urllib.request import urlretrieve

        def download(filename, source='http://yann.lecun.com/exdb/mnist/'):
            print("Downloading %s" % filename)
            urlretrieve(source + filename, filename)

        # We then define functions for loading MNIST images and labels.
        # For convenience, they also download the requested files if needed.
        import gzip

        def load_mnist_images(filename):
            if not os.path.exists(filename):
                download(filename)
            # Read the inputs in Yann LeCun's binary format.
            with gzip.open(filename, 'rb') as f:
                data = np.frombuffer(f.read(), np.uint8, offset=16)
            # The inputs are vectors now, we reshape them to monochrome 2D images,
            # following the shape convention: (examples, channels, rows, columns)
            data = data.reshape(-1, 1, 28, 28)
            # The inputs come as bytes, we convert them to float32 in range [0,1].
            # (Actually to range [0, 255/256], for compatibility to the version
            # provided at http://deeplearning.net/data/mnist/mnist.pkl.gz.)
            return data / np.float32(256)

        def load_mnist_labels(filename):
            if not os.path.exists(filename):
                download(filename)
            # Read the labels in Yann LeCun's binary format.
            with gzip.open(filename, 'rb') as f:
                data = np.frombuffer(f.read(), np.uint8, offset=8)
            # The labels are vectors of integers now, that's exactly what we want.
            return data

        # We can now download and read the training and test set images and labels.
        X_train = load_mnist_images('train-images-idx3-ubyte.gz')
        y_train = load_mnist_labels('train-labels-idx1-ubyte.gz')
        X_test = load_mnist_images('t10k-images-idx3-ubyte.gz')
        y_test = load_mnist_labels('t10k-labels-idx1-ubyte.gz')
        # We reserve the last 10000 training examples for validation.
        X_train, X_val = X_train[:-10000], X_train[-10000:]
        y_train, y_val = y_train[:-10000], y_train[-10000:]

        X_train = X_train.reshape(X_train.shape[0], 28 * 28)
        X_val = X_val.reshape(X_val.shape[0], 28 * 28)
        X_test = X_test.reshape(X_test.shape[0], 28 * 28)
    elif data_name=='cifar10':
        import pickle
        for f in range(1,5):
            batch=pickle.load(open(data_dir+'/cifar-10-batches-py/data_batch_'+str(f),'rb'))
            if f==1:
                X_train=np.array(batch['data'],dtype=np.float32)
                y_train=np.array(batch['labels'])
            else:
                X_train=np.concatenate((X_train,np.array(batch['data'],dtype=np.float32)))
                y_train=np.concatenate((y_train,np.array(batch['labels'])))
        batch=pickle.load(open(data_dir+'/cifar-10-batches-py/data_batch_5','rb'))
        X_val=np.array(batch['data'],dtype=np.float32)
        y_val=np.array(batch['labels'])
        batch=pickle.load(open(data_dir+'/cifar-10-batches-py/test_batch','rb'))
        X_test=np.array(batch['data'],dtype=np.float32)
        y_test=np.array(batch['labels'])
        if combine:
            X_train=np.concatenate((X_val,X_train))
            y_train=np.concatenate((y_val,y_train))



    data={}
    data['X_train']=X_train
    data['X_test']=X_test
    data['X_val']=X_val
    data['y_train']=y_train
    data['y_test']=y_test
    data['y_val']=y_val

    return data


# The optimization function that we want to optimize.
# It gets a numpy array x with shape (1,D) where D are the number of parameters
# and s which is the ratio of the training data that is used to
# evaluate this configuration
class svm_model:
    def __init__(self,name, data_dir, combine=False):
        self.data_dir=data_dir
        os.chdir(data_dir)
        self.name=name
        self.data=None
        self.orig_data=create_dataset(name,data_dir,combine)

    def compute_preprocessor(self,method):
        self.data={}
        if method=='min_max':
            transform=preprocessing.MinMaxScaler()
            self.data['X_train']=transform.fit_transform(self.orig_data['X_train'])
            self.data['X_val']=transform.transform(self.orig_data['X_val'])
            self.data['X_test']=transform.transform(self.orig_data['X_test'])
        elif method=='scaled':
            self.data['X_train']=preprocessing.scale(self.orig_data['X_train'])
            self.data['X_val']=preprocessing.scale(self.orig_data['X_val'])
            self.data['X_test']=preprocessing.scale(self.orig_data['X_test'])
        elif method=='normalized':
            self.data['X_train']=preprocessing.normalize(self.orig_data['X_train'])
            self.data['X_val']=preprocessing.normalize(self.orig_data['X_val'])
            self.data['X_test']=preprocessing.normalize(self.orig_data['X_test'])
        self.data['y_train']=self.orig_data['y_train']
        self.data['y_val']=self.orig_data['y_val']
        self.data['y_test']=self.orig_data['y_test']

    def run_solver(self, arm):
        kernel_map=dict(zip([1,2,3],['rbf','poly','sigmoid']))
        preprocess_map=dict(zip([1,2,3],['min_max','scaled','normalized']))
        self.compute_preprocessor(preprocess_map[arm['preprocessor']])
        print arm
        # Shuffle the data and split up the request subset of the training data
        # Train the SVM on the subset set
        if kernel_map[arm['kernel']]=='rbf':
            clf = svm.SVC(C=arm['C'], kernel=kernel_map[arm['kernel']], gamma=arm['gamma'])
        elif kernel_map[arm['kernel']]=='poly':
            clf = svm.SVC(C=arm['C'], kernel=kernel_map[arm['kernel']], gamma=arm['gamma'], coef0=arm['coef0'], degree=arm['degree'])
        elif kernel_map[arm['kernel']]=='sigmoid':
            clf = svm.SVC(C=arm['C'], kernel=kernel_map[arm['kernel']], gamma=arm['gamma'], coef0=arm['coef0'])
        clf.fit(self.data['X_train'], self.data['y_train'])

        # Validate this hyperparameter configuration on the full validation data
        #y_loss = 1 - clf.score(self.data['X_train'], self.data['y_train'])
        y_loss=1
        val_acc= clf.score(self.data['X_val'], self.data['y_val'])
        test_acc = clf.score(self.data['X_test'], self.data['y_test'])


        return y_loss,val_acc,test_acc

def main(params, data_dir):
    model=svm_model('cifar10',data_dir)
    if params is not None:
        for key in params:
            try:
                params[key] = int(params[key])
            except Exception:
                try:
                    params[key] = float(params[key])
                    if params[key]-np.floor(params[key])==0:
                        params[key]=int(params[key])
                except Exception:
                    pass

    train_loss,val_acc, test_acc = model.run_solver(params)
    return train_loss, val_acc, test_acc

if __name__ == "__main__":
    starttime = time.time()
    experiment_dir = os.getcwd()
    #sys.stdout = Logger(experiment_dir)
    args, params = benchmark_util.parse_cli()
    config = wrapping_util.load_experiment_config_file()
    data_dir=config.get('EXPERIMENT','data_dir')
    train_loss, val_acc, test_acc = main(params,data_dir)
    val_error=1-val_acc
    test_error = 1-test_acc
    duration = time.time() - starttime
    print "Result for ParamILS: %s, %f, 1, %f, %d, %s, %f" % \
        ("SAT", abs(duration), val_error, -1, "test_error", test_error)
