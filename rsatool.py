#!/usr/bin/env python2
import base64, fractions, optparse, random, requests, re
try:
    import gmpy
except ImportError as e:
    try:
        import gmpy2 as gmpy
    except ImportError:
        raise e

from pyasn1.codec.der import encoder
from pyasn1.type.univ import *

PEM_TEMPLATE = '-----BEGIN RSA PRIVATE KEY-----\n%s-----END RSA PRIVATE KEY-----\n'
DEFAULT_EXP = 65537

def factor_modulus(n, d, e):
    """
    Efficiently recover non-trivial factors of n

    See: Handbook of Applied Cryptography
    8.2.2 Security of RSA -> (i) Relation to factoring (p.287)

    http://www.cacr.math.uwaterloo.ca/hac/
    """
    #own the private key and public key, then return p and q
    t = (e * d - 1) #e*d = t+1
    				#e*d = k*n +1  when ed = 1 (mod n)
    s = 0

    while True:
        quotient, remainder = divmod(t, 2) #return (t//2, t%2) // means drop decimals

        if remainder != 0: # if t is odd then break
            break

        s += 1
        t = quotient

    found = False

    while not found:
        i = 1
        a = random.randint(1,n-1)

        while i <= s and not found:
            c1 = pow(a, pow(2, i-1, n) * t, n)
            c2 = pow(a, pow(2, i, n) * t, n)

            found = c1 != 1 and c1 != (-1 % n) and c2 == 1

            i += 1

    p = fractions.gcd(c1-1, n)
    q = n // p

    return p, q

class RSA:
    def __init__(self, p=None, q=None, n=None, d=None, m=None, c=None, e=DEFAULT_EXP):
        """
        Initialize RSA instance using primes (p, q)
        or modulus and private exponent (n, d)
        """
        if e:
            self.e = gmpy.mpz(e)
        else:
            self.e=None
        if m:
            self.m = gmpy.mpz(m)
        else:
            self.m=None
        if c:
            self.c = gmpy.mpz(c)
        else:
            self.c=None
        
        if p and q:
            assert gmpy.is_prime(p), 'p is not prime'
            assert gmpy.is_prime(q), 'q is not prime'

            self.p = gmpy.mpz(p)
            self.q = gmpy.mpz(q)
        elif n and d:   
            self.p, self.q = map(gmpy.mpz, factor_modulus(n, d, e))
        elif n:
            self.n = gmpy.mpz(n)
            self.p, self.q = map(int, factor_online(self.n))
        else:
            raise ArgumentError('+++++Input m++++')

        self._calc_values()

    def _calc_values(self):
        self.n = self.p * self.q

        if self.p != self.q:
            phi = (self.p - 1) * (self.q - 1)
        else:
            phi = (self.p ** 2) - self.p

        self.d = gmpy.invert(self.e, phi)
        
        if self.m:
            self.c = pow(self.m, self.e, self.n)
            self.hex_c = hex(self.c)[2:].decode('hex')
            self.hex_m = hex(self.m)[2:].decode('hex')
        if self.c:
            self.m = pow(self.c, self.d, self.n)
            self.hex_c = hex(self.c)[2:].decode('hex')
            self.hex_m = hex(self.m)[2:].decode('hex')
            
        # CRT-RSA precomputation
        # to accelerate the calculation 
        self.dP = self.d % (self.p - 1)
        self.dQ = self.d % (self.q - 1)
        self.qInv = gmpy.invert(self.q, self.p)
        # (p*qInv) %  

    def to_pem(self):
        """
        Return OpenSSL-compatible PEM encoded key
        """
        return (PEM_TEMPLATE % base64.encodestring(self.to_der()).decode()).encode()

    def to_der(self):
        """
        Return parameters as OpenSSL compatible DER encoded key
        """
        seq = Sequence()

        for x in [0, self.n, self.e, self.d, self.p, self.q, self.dP, self.dQ, self.qInv]:
            seq.setComponentByPosition(len(seq), Integer(x))

        return encoder.encode(seq)

    def dump(self, verbose, decode):
        vars = ['n', 'e', 'd', 'p', 'q', 'm', 'c']

        if verbose:
            vars += ['dP', 'dQ', 'qInv']
        for v in vars:
            self._dumpvar(v)
        if decode:
            print('hex_decode:')
            print('\tc = %s' % self.hex_c)
            print('\tm = %s' % self.hex_m)


    def _dumpvar(self, var):
        val = getattr(self, var)

        parts = lambda s, l: '\n'.join([s[i:i+l] for i in range(0, len(s), l)])

        if len(str(val)) <= 40:
            print('%s = %d (%#x)\n' % (var, val, val))
        else:
            print('%s =' % var)
            print(parts('%x' % val, 80) + '\n')

def factor_offline(n):
        print("failed to factor in http://factordb.com\nThe length of n is %s\nIt might need a very long time and sagemath is required" %(len(n)))
        try:
            from sage.all import factor
            p, q = map(int, re.split(r'\s*\*\s*', str(factor(n))))
            return (pp,qq )
        except ImportError as e:
            raise Exception("Can't factor n")
        
    

def factor_online(n):
    try:
        r = requests.get('http://factordb.com/index.php', params={'query':int(n)})
        # print(re.findall(r'>\d+<',r.text))
        numbers = re.findall(r'>\d+<',r.text)
        if len(numbers) is 3:
            p, q = numbers[1][1:-1], numbers[2][1:-1]
            return(p, q)
        else:
            raise Exception('p or q is not prime')
    except:
        p, q = factor_offline(n)


if __name__ == '__main__':
    parser = optparse.OptionParser()

    parser.add_option('-p', dest='p', help='prime', type='int')
    parser.add_option('-q', dest='q', help='prime', type='int')
    parser.add_option('-n', dest='n', help='modulus', type='int')
    parser.add_option('-d', dest='d', help='private exponent', type='int')
    parser.add_option('-e', dest='e', help='public exponent (default: %d)' % DEFAULT_EXP, type='int', default=DEFAULT_EXP)
    parser.add_option('-o', dest='filename', help='output filename')
    parser.add_option('-f', dest='format', help='output format (DER, PEM) (default: PEM)', type='choice', choices=['DER', 'PEM'], default='PEM')
    parser.add_option('-v', dest='verbose', help='also display CRT-RSA representation', action='store_true', default=False)
    
    parser.add_option('-m', dest='m', help='message',type='int', default=None)
    parser.add_option('-c', dest='c', help='ciphertext', type='int', default=None)
    parser.add_option('--decode', dest='decode', help='display hex decode of cipher and message',action='store_true',default=False)

    try:
        (options, args) = parser.parse_args()

        if options.p and options.q:
            print('Using (p, q) to initialise RSA instance\n')
            print type(options.m)
            rsa = RSA(p=options.p, q=options.q, e=options.e, c=options.c, m=options.m)
        elif options.n and options.d:
            print('Using (n, d) to initialise RSA instance\n')
            rsa = RSA(n=options.n, d=options.d, e=options.e)
        elif options.n and options.c:
            print('Using (n, c) to initialise RSA instance\n')
            rsa = RSA(n=options.n, c=options.c, e=options.e)
        # elif options.p and options.q and options.m:
        #     print('Using (p, q, m) to initialise RSA instance\n')
        # elif options.p and options.q and options.c:
        #     print('Using (p, q, c) to initialise RSA instance\n')
        # elif options.n and options
        else:
            parser.print_help()
            parser.error('Either (p, q) or (n, d) needs to be specified')

        rsa.dump(options.verbose, options.decode)

        if options.filename:
            print('Saving %s as %s' % (options.format, options.filename))


            if options.format == 'PEM':
                data = rsa.to_pem()
            elif options.format == 'DER':
                data = rsa.to_der()

            fp = open(options.filename, 'wb')
            fp.write(data)
            fp.close()

    except optparse.OptionValueError as e:
        parser.print_help()
        parser.error(e.msg)
