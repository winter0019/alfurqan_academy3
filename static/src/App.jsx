// This file will be compiled by Babel in the browser.
// It is the core of your frontend application.
// No need for "import React from 'react'" as it's loaded via CDN
const { useState, useEffect, useRef } = React;

// Hardcoded admin credentials for this MVP
const ADMIN_USERNAME = "admin";
const ADMIN_PASSWORD = "password";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [isAddingStudent, setIsAddingStudent] = useState(false);
  const [isAddingPayment, setIsAddingPayment] = useState(false);
  const [isGeneratingReceipt, setIsGeneratingReceipt] = useState(false);
  const [userId, setUserId] = useState(null);
  const receiptRef = useRef(null);

  // Use useRef to store Firebase instances that don't trigger re-renders
  const dbRef = useRef(null);
  const authRef = useRef(null);
  const isFirebaseInitialized = useRef(false);

  // Check if Firebase config is available before rendering anything
  if (typeof __firebase_config === 'undefined') {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-100 dark:bg-gray-900">
        <p className="text-xl text-gray-700 dark:text-gray-300">Loading configuration...</p>
      </div>
    );
  }

  // Initialize Firebase and handle authentication in a single, robust useEffect
  useEffect(() => {
    // Prevent re-initialization
    if (isFirebaseInitialized.current) return;

    try {
      const firebaseConfig = JSON.parse(__firebase_config);
      const app = firebase.initializeApp(firebaseConfig);
      authRef.current = firebase.auth(app);
      dbRef.current = firebase.firestore(app);

      // Sign in using the provided token or anonymously
      const setupAuth = async () => {
        try {
          if (__initial_auth_token) {
            await authRef.current.signInWithCustomToken(__initial_auth_token);
          } else {
            await authRef.current.signInAnonymously();
          }
        } catch (e) {
          console.error("Authentication error: ", e);
        }
      };
      setupAuth();

      // Listen for auth state changes to get the user ID
      const unsubscribeAuth = authRef.current.onAuthStateChanged(user => {
        if (user) {
          setUserId(user.uid);
          console.log("Firebase Auth State Changed: Logged in");
        } else {
          setUserId(null);
          console.log("Firebase Auth State Changed: Logged out");
        }
      });
      isFirebaseInitialized.current = true;
      return () => unsubscribeAuth();

    } catch (e) {
      console.error("Error initializing Firebase or signing in: ", e);
    }
  }, []);

  // Fetch and listen for student data once authenticated and logged in
  useEffect(() => {
    if (dbRef.current && userId && isLoggedIn) {
      const appId = typeof __app_id !== 'undefined' ? __app_id : 'school-mvp';
      console.log("Fetching data for user:", userId);
      const studentsCollectionRef = dbRef.current.collection(`artifacts/${appId}/users/${userId}/students`);
      const unsubscribe = studentsCollectionRef.onSnapshot((snapshot) => {
        const studentsList = snapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));
        setStudents(studentsList);
        setLoading(false);
      }, (error) => {
        console.error("Error fetching students: ", error);
        setLoading(false);
      });
      return () => unsubscribe();
    }
  }, [userId, isLoggedIn]);


  const handleLogin = (username, password) => {
    if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
      setIsLoggedIn(true);
    } else {
      const messageBox = document.createElement('div');
      messageBox.className = "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white p-6 rounded-lg shadow-xl z-50 dark:bg-gray-800";
      messageBox.innerHTML = `
        <h3 class="text-xl font-bold mb-2 text-gray-900 dark:text-white">Login Failed</h3>
        <p class="text-gray-600 dark:text-gray-300">Invalid credentials. Please try again.</p>
        <button onclick="this.parentNode.remove()" class="mt-4 w-full px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">
          OK
        </button>
      `;
      document.body.appendChild(messageBox);
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
  };

  const handleAddStudentClick = () => {
    setIsAddingStudent(true);
    setIsAddingPayment(false);
    setIsGeneratingReceipt(false);
    setSelectedStudent(null);
  };

  const handleAddPaymentClick = (student) => {
    setIsAddingPayment(true);
    setIsAddingStudent(false);
    setIsGeneratingReceipt(false);
    setSelectedStudent(student);
  };

  const handleGenerateReceiptClick = (student) => {
    setIsGeneratingReceipt(true);
    setIsAddingPayment(false);
    setIsAddingStudent(false);
    setSelectedStudent(student);
  };

  const handleBack = () => {
    setIsAddingStudent(false);
    setIsAddingPayment(false);
    setIsGeneratingReceipt(false);
    setSelectedStudent(null);
  };

  const addStudent = async (studentData) => {
    if (!dbRef.current || !userId) return;
    try {
      const appId = typeof __app_id !== 'undefined' ? __app_id : 'school-mvp';
      const studentsCollectionRef = dbRef.current.collection(`artifacts/${appId}/users/${userId}/students`);
      await studentsCollectionRef.add({
        ...studentData,
        isPaid: false,
        payments: []
      });
      handleBack();
    } catch (e) {
      console.error("Error adding document: ", e);
    }
  };

  const recordPayment = async (studentId, amount) => {
    if (!dbRef.current || !userId) return;
    try {
      const appId = typeof __app_id !== 'undefined' ? __app_id : 'school-mvp';
      const studentDocRef = dbRef.current.collection(`artifacts/${appId}/users/${userId}/students`).doc(studentId);
      const studentData = (await studentDocRef.get()).data();
      await studentDocRef.update({
        isPaid: true,
        payments: [...(studentData.payments || []), { amount: parseFloat(amount), date: new Date().toISOString() }]
      });
      handleBack();
    } catch (e) {
      console.error("Error updating document: ", e);
    }
  };

  const generateAndDownloadReceipt = () => {
    if (receiptRef.current && window.html2canvas && window.jsPDF) {
      const receiptElement = receiptRef.current;
      html2canvas(receiptElement).then(canvas => {
        const imgData = canvas.toDataURL('image/png');
        const pdf = new jspdf.jsPDF('p', 'mm', 'a4');
        const imgProps = pdf.getImageProperties(imgData);
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

        pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
        pdf.save(`Receipt_${selectedStudent.admissionNumber}.pdf`);
      });
    }
  };

  const filteredStudents = students
    .filter(student => {
      const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          student.admissionNumber.toLowerCase().includes(searchTerm.toLowerCase());
      if (activeTab === 'all') {
        return matchesSearch;
      } else if (activeTab === 'paid') {
        return student.isPaid && matchesSearch;
      } else if (activeTab === 'unpaid') {
        return !student.isPaid && matchesSearch;
      }
      return false;
    });

  const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const handleSubmit = (e) => {
      e.preventDefault();
      handleLogin(username, password);
    };
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900">
        <div className="w-full max-w-sm p-8 space-y-6 bg-white rounded-xl shadow-lg dark:bg-gray-800">
          <h2 className="text-3xl font-bold text-center text-gray-900 dark:text-white">Admin Login</h2>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
              <input type="text" className="w-full px-4 py-2 mt-1 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
              <input type="password" className="w-full px-4 py-2 mt-1 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className="w-full px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">Log In</button>
          </form>
        </div>
      </div>
    );
  };

  const StudentList = () => {
    return (
      <div className="flex flex-col gap-4">
        {loading ? (
          <div className="flex justify-center items-center h-48">
            <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
        ) : (
          filteredStudents.length > 0 ? (
            filteredStudents.map(student => (
              <div key={student.id} className="p-4 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer flex justify-between items-center dark:bg-gray-800">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{student.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">ID: {student.admissionNumber}</p>
                  <p className={`text-sm font-medium ${student.isPaid ? 'text-green-600' : 'text-red-600'}`}>Status: {student.isPaid ? 'Paid' : 'Unpaid'}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">User ID: {userId}</p>
                </div>
                <div className="flex gap-2">
                  {!student.isPaid && (
                    <button onClick={() => handleAddPaymentClick(student)} className="px-3 py-1 text-xs font-semibold text-white bg-green-500 rounded-lg hover:bg-green-600 transition-colors">Add Payment</button>
                  )}
                  {student.isPaid && (
                    <button onClick={() => handleGenerateReceiptClick(student)} className="px-3 py-1 text-xs font-semibold text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors">Receipt</button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-center text-gray-500 dark:text-gray-400 mt-8">No students found matching your criteria.</p>
          )
        )}
      </div>
    );
  };

  const AddStudentForm = () => {
    const [name, setName] = useState('');
    const [admissionNumber, setAdmissionNumber] = useState('');
    const handleSubmit = (e) => {
      e.preventDefault();
      addStudent({ name, admissionNumber });
    };
    return (
      <div className="p-6 bg-white rounded-xl shadow-lg dark:bg-gray-800">
        <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">New Student Registration</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Student Name</label>
            <input type="text" className="w-full px-4 py-2 mt-1 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Admission Number</label>
            <input type="text" className="w-full px-4 py-2 mt-1 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={admissionNumber} onChange={(e) => setAdmissionNumber(e.target.value)} required />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="w-full px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">Add Student</button>
            <button type="button" onClick={handleBack} className="w-full px-4 py-2 text-gray-800 bg-gray-200 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 transition-colors">Cancel</button>
          </div>
        </form>
      </div>
    );
  };

  const AddPaymentForm = () => {
    const [amount, setAmount] = useState('');
    const handleSubmit = (e) => {
      e.preventDefault();
      recordPayment(selectedStudent.id, amount);
    };
    return (
      <div className="p-6 bg-white rounded-xl shadow-lg dark:bg-gray-800">
        <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Record Payment for {selectedStudent.name}</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Payment Amount</label>
            <input type="number" className="w-full px-4 py-2 mt-1 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="w-full px-4 py-2 text-white bg-green-600 rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 transition-colors">Record Payment</button>
            <button type="button" onClick={handleBack} className="w-full px-4 py-2 text-gray-800 bg-gray-200 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 transition-colors">Cancel</button>
          </div>
        </form>
      </div>
    );
  };

  const ReceiptGenerator = () => {
    const latestPayment = selectedStudent.payments && selectedStudent.payments.length > 0
      ? selectedStudent.payments[selectedStudent.payments.length - 1]
      : null;
    if (!latestPayment) {
        return (
            <div className="p-6 bg-white rounded-xl shadow-lg dark:bg-gray-800">
                <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Receipt Not Found</h3>
                <p className="text-gray-500 dark:text-gray-400">There is no payment history for this student.</p>
                <div className="flex gap-2 mt-4">
                    <button onClick={handleBack} className="px-4 py-2 text-gray-800 bg-gray-200 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 transition-colors">Back</button>
                </div>
            </div>
        );
    }
    return (
      <div className="p-6 space-y-4">
        <div ref={receiptRef} className="p-8 border-4 border-gray-300 rounded-xl bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-xl">
          <h2 className="text-3xl font-bold mb-4 text-center">Payment Receipt</h2>
          <div className="border-t border-b border-gray-300 py-4 mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold">Student Name:</span>
              <span>{selectedStudent.name}</span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold">Admission Number:</span>
              <span>{selectedStudent.admissionNumber}</span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold">Date:</span>
              <span>{new Date(latestPayment.date).toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="font-semibold">Payment Amount:</span>
              <span className="text-xl font-bold text-green-600">${latestPayment.amount.toFixed(2)}</span>
            </div>
          </div>
          <p className="text-center text-sm italic text-gray-500 dark:text-gray-400">Thank you for your payment.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <button onClick={generateAndDownloadReceipt} className="w-full px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">Download PDF</button>
          <button onClick={handleBack} className="w-full px-4 py-2 text-gray-800 bg-gray-200 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 transition-colors">Cancel</button>
        </div>
      </div>
    );
  };
  if (!isLoggedIn) {
    return <Login />;
  }
  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white font-sans p-4 sm:p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-bold">School Management MVP</h1>
        <button onClick={handleLogout} className="px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors">Logout</button>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 space-y-6">
        {isAddingStudent || isAddingPayment || isGeneratingReceipt ? (
          <>
            {isAddingStudent && <AddStudentForm />}
            {isAddingPayment && <AddPaymentForm />}
            {isGeneratingReceipt && <ReceiptGenerator />}
          </>
        ) : (
          <>
            <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
              <div className="flex-1 w-full">
                <input type="text" placeholder="Search by name or admission number..." className="w-full px-4 py-2 text-gray-900 bg-gray-50 rounded-lg dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
              </div>
              <button onClick={handleAddStudentClick} className="w-full sm:w-auto px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">+ Add New Student</button>
            </div>
            <div className="flex flex-wrap gap-2 text-sm font-semibold text-gray-500 dark:text-gray-400">
              <button onClick={() => setActiveTab('all')} className={`px-3 py-1 rounded-full ${activeTab === 'all' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>All ({students.length})</button>
              <button onClick={() => setActiveTab('paid')} className={`px-3 py-1 rounded-full ${activeTab === 'paid' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>Paid ({students.filter(s => s.isPaid).length})</button>
              <button onClick={() => setActiveTab('unpaid')} className={`px-3 py-1 rounded-full ${activeTab === 'unpaid' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>Unpaid ({students.filter(s => !s.isPaid).length})</button>
            </div>
            <StudentList />
          </>
        )}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
