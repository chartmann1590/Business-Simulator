// Map employee roles/titles to avatar files
const avatarMapping = {
  // Role-based mappings
  'CEO': 'office_char_08_exec.png',
  'CTO': 'office_char_08_exec.png',
  'COO': 'office_char_08_exec.png',
  'CFO': 'office_char_13_finance.png',
  'Manager': 'office_char_01_manager.png',
  'Employee': 'office_char_02_dev.png',
  
  // Title-based mappings (more specific)
  'Chief Executive Officer': 'office_char_08_exec.png',
  'Chief Technology Officer': 'office_char_08_exec.png',
  'Chief Operating Officer': 'office_char_08_exec.png',
  'Chief Financial Officer': 'office_char_13_finance.png',
  'Executive': 'office_char_08_exec.png',
  'Manager': 'office_char_01_manager.png',
  'Project Manager': 'office_char_11_pm.png',
  'Developer': 'office_char_02_dev.png',
  'Software Engineer': 'office_char_12_engineer.png',
  'Engineer': 'office_char_12_engineer.png',
  'HR': 'office_char_03_hr.png',
  'Human Resources': 'office_char_03_hr.png',
  'Receptionist': 'office_char_04_reception.png',
  'IT': 'office_char_05_it.png',
  'Information Technology': 'office_char_05_it.png',
  'Accountant': 'office_char_06_accounting.png',
  'Accounting': 'office_char_06_accounting.png',
  'Finance': 'office_char_13_finance.png',
  'Intern': 'office_char_07_intern.png',
  'Designer': 'office_char_09_designer.png',
  'Support': 'office_char_10_support.png',
  'Customer Support': 'office_char_10_support.png',
  'Admin': 'office_char_14_admin.png',
  'Administrator': 'office_char_14_admin.png',
  'Marketing': 'office_char_15_marketing.png',
  'Lawyer': 'office_char_16_lawyer.png',
  'Legal': 'office_char_16_lawyer.png',
  'Assistant': 'office_char_17_assistant.png',
  'Data': 'office_char_18_data.png',
  'Data Analyst': 'office_char_18_data.png',
  'Sales': 'office_char_19_sales.png',
  'Security': 'office_char_20_security.png',
};

const allAvatars = [
  'office_char_01_manager.png',
  'office_char_02_dev.png',
  'office_char_03_hr.png',
  'office_char_04_reception.png',
  'office_char_05_it.png',
  'office_char_06_accounting.png',
  'office_char_07_intern.png',
  'office_char_08_exec.png',
  'office_char_09_designer.png',
  'office_char_10_support.png',
  'office_char_11_pm.png',
  'office_char_12_engineer.png',
  'office_char_13_finance.png',
  'office_char_14_admin.png',
  'office_char_15_marketing.png',
  'office_char_16_lawyer.png',
  'office_char_17_assistant.png',
  'office_char_18_data.png',
  'office_char_19_sales.png',
  'office_char_20_security.png',
];

export function getAvatarPath(employee) {
  // First try exact title match
  if (employee.title && avatarMapping[employee.title]) {
    return `/avatars/${avatarMapping[employee.title]}`;
  }
  
  // Then try role match
  if (employee.role && avatarMapping[employee.role]) {
    return `/avatars/${avatarMapping[employee.role]}`;
  }
  
  // Try partial title match (case insensitive)
  if (employee.title) {
    const titleLower = employee.title.toLowerCase();
    for (const [key, value] of Object.entries(avatarMapping)) {
      if (titleLower.includes(key.toLowerCase()) || key.toLowerCase().includes(titleLower)) {
        return `/avatars/${value}`;
      }
    }
  }
  
  // Try department match
  if (employee.department) {
    const deptLower = employee.department.toLowerCase();
    for (const [key, value] of Object.entries(avatarMapping)) {
      if (deptLower.includes(key.toLowerCase())) {
        return `/avatars/${value}`;
      }
    }
  }
  
  // Fallback: use employee ID to consistently assign an avatar
  if (employee.id) {
    const avatarIndex = (employee.id - 1) % allAvatars.length;
    return `/avatars/${allAvatars[avatarIndex]}`;
  }
  
  // Final fallback
  return `/avatars/${allAvatars[0]}`;
}


