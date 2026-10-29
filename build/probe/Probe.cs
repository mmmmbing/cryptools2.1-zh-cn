using System;
using System.Reflection;
using System.Resources;
using System.Collections;

class Probe {
    static int Main(string[] a) {
        try {
            var asm = Assembly.LoadFile(a[0]);
            Console.WriteLine("FullName: " + asm.FullName);
            Console.WriteLine("Culture : '" + asm.GetName().CultureName + "'");
            Console.WriteLine("Version : " + asm.GetName().Version);
            foreach (var n in asm.GetManifestResourceNames()) {
                Console.WriteLine("RES: " + n);
                using (var s = asm.GetManifestResourceStream(n))
                using (var r = new ResourceReader(s)) {
                    int c = 0; IDictionaryEnumerator e = r.GetEnumerator();
                    while (e.MoveNext()) {
                        c++;
                        if (c <= 4) {
                            var v = e.Value;
                            string disp = v == null ? "<null>" : (v is string ? (string)v : "<" + v.GetType().Name + ">");
                            if (disp.Length > 46) disp = disp.Substring(0, 46);
                            Console.WriteLine("   [" + e.Key + "] " + disp);
                        }
                    }
                    Console.WriteLine("   total=" + c);
                }
            }
            return 0;
        } catch (Exception ex) { Console.WriteLine("ERR: " + ex.Message); return 1; }
    }
}
