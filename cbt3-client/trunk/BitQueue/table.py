'''
table formatter
'''

class Formatter:
    def __init__(self,format):
        self.set_format(format)

    def set_format(self,format):
        self._format = format

    def format(self,data):
        return data

class ColumnFormatter(Formatter):

    def set_format(self,format):
        Formatter.set_format(self,format)
        self._align = self._format[0].lower()
        try:
            self.width = int(self._format[1:])
        except ValueError:
            self.width = 0

    def format(self,data):
        if self.width > 0:
            data = data[:self.width]
            if self._align == 'c':
                data = data.center(self.width)
            elif self._align == 'r':
                data = ' '*(self.width-len(data))+data
        return data+' '*(self.width-len(data))

class RowFormatter(Formatter):
    def set_format(self,format):
        Formatter.set_format(self,format)
        self.columns = []
        for col in self._format.split(':'):
            self.columns.append(ColumnFormatter(col))

    def format(self,data):
        s = ''
        for formatter,item in map(None,self.columns,data):
            if formatter is None:
                break
            s += formatter.format(str(item))+' '
        return s[:-1]

class TableFormatter(RowFormatter):
    def format(self,data):
        width = []
        formatted_data = []
        for i in range(len(self.columns)):
            width.append(0)
        for line in data:
            i = 0
            formatted_line = []
            for formatter,item in map(None,self.columns,line):
                if formatter is None:
                    break
                formatted_item = formatter.format(str(item))
                width[i] = max(width[i],len(formatted_item))
                formatted_line.append(formatted_item)
                i += 1
            formatted_data.append(formatted_line)
        s = ''
        for formatted_line in formatted_data:
            i = 0
            for formatted_item in formatted_line:
                s += formatted_item+' '*(width[i]-len(formatted_item))+' '
                i += 1
            s = s[:-1]+'\n'
        return s[:-1]

if __name__ == '__main__':
    data = [
            ['a','0',0],
            ['b','1',1],
            ['0123456789012345678901234567890','1',1000],
           ]
    table = TableFormatter('l20:r30:c27')
    print table.format(data)
