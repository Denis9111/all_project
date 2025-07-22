''' прога копирования файлов '''

import os, time

source = ['/Users/m1pro/IT/test1', '/Users/m1pro/IT/test2']
target_dir = '/Users/m1pro/IT/rescopy'

target = target_dir + os.sep + time.strftime('%Y-%m-%d_%H-%M-%S') + '.zip'
print(target)

zip_command = "zip -qr {0} {1}".format(target, ' '.join(source))
print(zip_command)

if os.system(zip_command) == 0:
    print('Резервная копия успешно создана в', target)
    print(target)
else:
    print('Создание резервной копии НЕ УДАЛОСЬ')

__version__ = '1.0'

print(__doc__)